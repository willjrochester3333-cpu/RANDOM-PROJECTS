// Flight logger: 64-byte LogRecords appended to the 16 MB W25Q128 without ever blocking the 500 Hz loop.
//  * the region ahead of the write pointer is verified/erased while the rocket sits on the pad
//  * full pages are queued in RAM and programmed one per loop when the flash is idle
//  * the last 0.5 s before launch is kept in a RAM ring and written once the launch is detected
#pragma once
#include <cstdint>

#include "../hw/sensors.hpp"
#include "kestrel/types.hpp"

namespace app {

constexpr uint8_t kHeaderState = 0xF0;   // session header record (see docs/FIRMWARE.md)
constexpr uint8_t kFillerState = 0xFE;   // padding record (skip when decoding)

class Logger {
public:
    bool init(hw::W25q* flash);              // finds the append point (binary search)
    void start_session(uint8_t motor_index, uint32_t flight_no, uint16_t fw_version, uint64_t now_us);
    void log(const kestrel::LogRecord& r, kestrel::FlightState st);   // call every loop; decimates by state
    void service(bool on_pad);               // call every loop: programs/erases/verifies, one step at a time
    uint32_t write_addr() const { return wr_; }
    uint32_t ready_bytes() const { return erased_end_ > wr_ ? erased_end_ - wr_ : 0; }
    uint32_t dropped() const { return dropped_; }
    bool full() const { return wr_ + 64 > hw::W25q::kSize; }
    bool ok() const { return ok_; }
    bool idle() const { return q_count_ == 0 && fill_ == 0; }
    void flush_partial();                    // pad the current page and queue it (on landing / CLI)
    // CLI helpers (only when not flying)
    uint32_t count_records() const { return wr_ / 64; }
    void erase_all_blocking();

private:
    void push(const kestrel::LogRecord& r);
    void queue_page();
    bool is_erased_record(uint32_t idx);

    hw::W25q* f_{nullptr};
    bool ok_{false};
    uint32_t wr_{0};                 // next record address (flash)
    uint32_t erased_end_{0};         // [wr_, erased_end_) verified blank
    uint32_t verify_addr_{0};        // scanner position
    bool erasing_{false};
    // page assembly + queue
    uint8_t page_[256]{};
    uint32_t page_addr_{0};
    int fill_{0};
    static constexpr int kQ = 128;
    uint8_t q_[kQ][256]{};
    uint32_t q_addr_[kQ]{};
    int q_head_{0}, q_count_{0};
    bool programming_{false};
    // pre-launch ring
    static constexpr int kRing = 256;
    kestrel::LogRecord ring_[kRing]{};
    int ring_head_{0}, ring_n_{0};
    kestrel::FlightState last_state_{kestrel::FlightState::BOOT};
    uint32_t decim_{0};
    uint32_t dropped_{0};
    uint32_t t_landed_ms_{0};
};

}  // namespace app
