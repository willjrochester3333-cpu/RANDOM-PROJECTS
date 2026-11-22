#include "logger.hpp"

#include <cstring>

#include "../logic/servo_map.hpp"
#include "pico/stdlib.h"

namespace app {

using kestrel::FlightState;
using kestrel::LogRecord;

namespace {
constexpr uint32_t kAheadBytes = 1024u * 1024u;   // keep 1 MB blank ahead of the write pointer (~30 s at 500 Hz)
}

bool Logger::is_erased_record(uint32_t idx) {
    uint8_t b[8];
    f_->read(idx * 64u, b, 8);
    for (uint8_t v : b)
        if (v != 0xFF) return false;
    return true;
}

bool Logger::init(hw::W25q* flash) {
    f_ = flash;
    ok_ = f_ && f_->ok();
    if (!ok_) return false;
    // records are appended contiguously from address 0 -> first erased record by binary search
    uint32_t lo = 0, hi = hw::W25q::kSize / 64u;   // answer in [lo, hi]
    while (lo < hi) {
        const uint32_t mid = lo + (hi - lo) / 2;
        if (is_erased_record(mid)) hi = mid; else lo = mid + 1;
    }
    wr_ = lo * 64u;
    // resume mid-page: the page buffer starts with 0xFF over the records already in flash (programming 1s
    // into NOR flash changes nothing), so there are never erased-looking holes inside the written region
    page_addr_ = wr_ & ~255u;
    fill_ = static_cast<int>((wr_ - page_addr_) / 64u);
    std::memset(page_, 0xFF, sizeof page_);
    erased_end_ = wr_;                       // nothing ahead is trusted until verified
    verify_addr_ = wr_;
    return true;
}

void Logger::start_session(uint8_t motor_index, uint32_t flight_no, uint16_t fw_version, uint64_t now_us) {
    LogRecord h{};
    std::memset(&h, 0, sizeof h);
    h.t_ms = static_cast<uint32_t>(now_us / 1000u);
    h.state = kHeaderState;
    h.flags = motor_index;
    h.gyro_cdps[0] = static_cast<int16_t>(fw_version);
    h.gyro_cdps[1] = static_cast<int16_t>(flight_no & 0x7FFF);
    h.crc16 = kestrel::crc16_ccitt(&h, 62);
    push(h);
}

void Logger::push(const LogRecord& r) {
    if (!ok_ || full()) { ++dropped_; return; }
    std::memcpy(page_ + fill_ * 64, &r, 64);
    wr_ = page_addr_ + static_cast<uint32_t>(fill_ + 1) * 64u;
    if (++fill_ == 4) queue_page();
}

void Logger::queue_page() {
    if (fill_ == 0) return;
    for (int i = fill_; i < 4; ++i) {        // pad with filler records (never 0xFF: see init())
        std::memset(page_ + i * 64, 0x00, 64);
        page_[i * 64 + 4] = kFillerState;
    }
    if (q_count_ == kQ) {
        ++dropped_;                          // queue overflow (should never happen at our data rates)
    } else {
        const int slot = (q_head_ + q_count_) % kQ;
        std::memcpy(q_[slot], page_, 256);
        q_addr_[slot] = page_addr_;
        ++q_count_;
    }
    page_addr_ += 256u;
    wr_ = page_addr_;
    fill_ = 0;
    std::memset(page_, 0xFF, sizeof page_);
}

void Logger::flush_partial() { queue_page(); }

void Logger::log(const LogRecord& r, FlightState st) {
    // per-state decimation of the 500 Hz stream
    uint32_t every = 250;                    // 2 Hz default (boot / calibrating / error)
    switch (st) {
        case FlightState::READY: every = 50; break;                // 10 Hz (+ full-rate RAM ring)
        case FlightState::BOOST:
        case FlightState::COAST: every = 1; break;                 // 500 Hz
        case FlightState::DESCENT: every = 10; break;              // 50 Hz
        case FlightState::LANDED:
            if (t_landed_ms_ == 0) t_landed_ms_ = r.t_ms;
            every = (r.t_ms - t_landed_ms_ < 600000u) ? 100 : 2500;   // 5 Hz for 10 min, then every 5 s
            break;
        default: break;
    }
    // launch: dump the pre-launch ring first so the log starts ~0.5 s before ignition was detected
    if (st == FlightState::BOOST && last_state_ != FlightState::BOOST) {
        const int start = (ring_head_ - ring_n_ + kRing) % kRing;
        for (int i = 0; i < ring_n_; ++i) push(ring_[(start + i) % kRing]);
        ring_n_ = 0;
        decim_ = 0;
    }
    last_state_ = st;
    if (st == FlightState::READY || st == FlightState::CALIBRATING) {
        ring_[ring_head_] = r;
        ring_head_ = (ring_head_ + 1) % kRing;
        if (ring_n_ < kRing) ++ring_n_;
    }
    if (decim_++ % every == 0) push(r);
}

void Logger::service(bool on_pad) {
    if (!ok_) return;
    if (programming_ || erasing_) {
        if (f_->busy()) return;
        programming_ = erasing_ = false;
    }
    // 1) program queued pages (only into verified-blank flash)
    if (q_count_ > 0) {
        const uint32_t a = q_addr_[q_head_];
        if (a + 256u <= erased_end_) {
            f_->program_page_start(a, q_[q_head_], 256);
            programming_ = true;
            q_head_ = (q_head_ + 1) % kQ;
            --q_count_;
            return;
        }
        if (!on_pad) {                       // in flight and nothing verified: write anyway (chip ships erased)
            f_->program_page_start(a, q_[q_head_], 256);
            programming_ = true;
            q_head_ = (q_head_ + 1) % kQ;
            --q_count_;
            return;
        }
    }
    // 2) on the pad: verify / erase the region ahead, one 256-byte chunk per loop
    if (on_pad && erased_end_ < hw::W25q::kSize && erased_end_ < wr_ + kAheadBytes) {
        if (verify_addr_ < erased_end_) verify_addr_ = erased_end_;
        uint8_t b[256];
        f_->read(verify_addr_, b, 256);
        bool blank = true;
        for (uint8_t v : b) blank &= (v == 0xFF);
        if (blank) {
            verify_addr_ += 256u;
            erased_end_ = verify_addr_;
        } else {
            const uint32_t sector = verify_addr_ & ~(hw::W25q::kSector - 1u);
            if (sector < wr_ && verify_addr_ >= wr_) {
                // garbage after the append point inside the current sector: continue in the next sector
                // (records still in the page buffer move with it; the garbage fails its CRC when decoded)
                verify_addr_ = sector + hw::W25q::kSector;
                page_addr_ = verify_addr_;
                wr_ = page_addr_ + static_cast<uint32_t>(fill_) * 64u;
                erased_end_ = verify_addr_;
            } else {
                f_->erase_sector_start(sector);
                erasing_ = true;
                verify_addr_ = sector;
                erased_end_ = sector;
            }
        }
    }
}

void Logger::erase_all_blocking() {
    if (!ok_) return;
    f_->erase_chip_start();
    while (f_->busy()) sleep_ms(100);
    wr_ = page_addr_ = erased_end_ = verify_addr_ = 0;
    fill_ = 0;
    q_count_ = 0;
    std::memset(page_, 0xFF, sizeof page_);
}

}  // namespace app
