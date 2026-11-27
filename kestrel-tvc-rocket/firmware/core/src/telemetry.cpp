#include "kestrel/telemetry.hpp"

#include <cmath>
#include <cstring>

namespace kestrel::tlm {

uint16_t crc_x25(const uint8_t* p, size_t n, uint16_t crc) {
    for (size_t i = 0; i < n; ++i) {
        uint8_t tmp = static_cast<uint8_t>(p[i] ^ static_cast<uint8_t>(crc & 0xFFu));
        tmp = static_cast<uint8_t>(tmp ^ static_cast<uint8_t>(tmp << 4));
        crc = static_cast<uint16_t>((crc >> 8) ^ (static_cast<uint16_t>(tmp) << 8) ^ (static_cast<uint16_t>(tmp) << 3) ^
                                    (tmp >> 4));
    }
    return crc;
}

uint8_t crc_extra(uint8_t msgid) {
    switch (msgid) {
        case kMsgHeartbeat: return kCrcHeartbeat;
        case kMsgRadioStatus: return kCrcRadioStatus;
        case kMsgFast: return kCrcFast;
        case kMsgSlow: return kCrcSlow;
        default: return 0;
    }
}

namespace {
bool known(uint8_t msgid) {
    return msgid == kMsgHeartbeat || msgid == kMsgRadioStatus || msgid == kMsgFast || msgid == kMsgSlow;
}
uint16_t frame_crc(const uint8_t* frame, uint8_t len, uint8_t msgid) {
    uint16_t c = crc_x25(frame + 1, static_cast<size_t>(len) + 5u);
    const uint8_t extra = crc_extra(msgid);
    return crc_x25(&extra, 1, c);
}
}  // namespace

size_t encode(uint8_t msgid, uint8_t seq, const void* payload, uint8_t payload_len, uint8_t* out, uint8_t sysid,
              uint8_t compid) {
    if (payload_len > kMaxPayload) return 0;
    out[0] = kStx;
    out[1] = payload_len;
    out[2] = seq;
    out[3] = sysid;
    out[4] = compid;
    out[5] = msgid;
    if (payload_len) std::memcpy(out + 6, payload, payload_len);
    const uint16_t c = frame_crc(out, payload_len, msgid);
    out[6 + payload_len] = static_cast<uint8_t>(c & 0xFFu);
    out[7 + payload_len] = static_cast<uint8_t>(c >> 8);
    return static_cast<size_t>(payload_len) + kOverhead;
}

void Decoder::drop(size_t k) {
    if (k >= n_) { n_ = 0; return; }
    std::memmove(win_, win_ + k, n_ - k);
    n_ -= k;
}

bool Decoder::feed(uint8_t b) {
    if (n_ == sizeof(win_)) drop(1);            // cannot happen with valid lengths; keeps the window bounded
    win_[n_++] = b;
    for (;;) {
        size_t k = 0;
        while (k < n_ && win_[k] != kStx) ++k;  // skip to the next start byte
        if (k) drop(k);
        if (n_ < 2) return false;
        const uint8_t len = win_[1];
        if (len > kMaxPayload) { ++bad_; drop(1); continue; }
        const size_t need = static_cast<size_t>(len) + kOverhead;
        if (n_ < need) return false;
        const uint8_t id = win_[5];
        const uint16_t got = static_cast<uint16_t>(win_[6 + len] | (win_[7 + len] << 8));
        if (known(id) && frame_crc(win_, len, id) == got) {
            std::memcpy(frame_, win_, need);
            ++good_;
            drop(need);
            return true;
        }
        ++bad_;
        drop(1);                                // false start or damaged frame: look for the next 0xFE
    }
}

void make_fast(const LogRecord& r, FastPayload& f) {
    f.t_ms = r.t_ms;
    f.state = r.state;
    f.flags = r.flags;
    for (int i = 0; i < 3; ++i) {
        f.gyro_cdps[i] = r.gyro_cdps[i];
        f.accel_cmss[i] = r.accel_cmss[i];
        f.q_i16[i] = r.q_i16[i];
    }
    f.alt_m = r.alt_m;
    const float v = std::fmax(-32767.0f, std::fmin(32767.0f, r.vz_ms * 100.0f));
    f.vz_cms = static_cast<int16_t>(std::lround(v));
    f.tilt_cdeg = r.tilt_cdeg;
    f.gimbal_cdeg[0] = r.gimbal_y_cdeg;
    f.gimbal_cdeg[1] = r.gimbal_z_cdeg;
    for (int k = 0; k < 4; ++k) f.tab_qdeg[k] = r.tab_qdeg[k];
    f.roll_cdeg = r.roll_cdeg;
}

Rates rates_for(FlightState st, float t_since_landed_s, int budget_level) {
    switch (st) {
        case FlightState::BOOST:
        case FlightState::COAST:
        case FlightState::DESCENT:
            if (budget_level == 0) return {10, 100};       // 50 Hz motion + 5 Hz GPS/power
            if (budget_level == 1) return {50, 250};       // 10 Hz + 2 Hz
            return {0, 2500};                              // 0.2 Hz beacon
        case FlightState::READY:
            if (budget_level == 0) return {500, 1000};     // 1 Hz + 0.5 Hz while waiting on the pad
            if (budget_level == 1) return {0, 1000};
            return {0, 5000};
        case FlightState::LANDED:
            if (budget_level >= 2) return {0, 5000};
            if (budget_level == 0 && t_since_landed_s < 60.0f) return {0, 500};   // 1 Hz position for a minute
            return {0, 2500};                              // then a 0.2 Hz recovery beacon
        case FlightState::BOOT:
        case FlightState::CALIBRATING:
        case FlightState::ERROR:
        default:
            if (budget_level == 0) return {0, 500};
            if (budget_level == 1) return {0, 2500};
            return {0, 5000};
    }
}

float frame_airtime_s(size_t frame_bytes) {
    // SiK at 64 kbit/s: 8 ticks/byte, packet latency (8 + 10/2) * 8 + 13 = 117 ticks, 2-byte trailer, 16 us ticks
    const float ticks = 117.0f + static_cast<float>(frame_bytes + 2u) * 8.0f;
    return ticks * 16e-6f;
}

void AirtimeBudget::tick(uint32_t now_ms) {
    if (!started_) {
        started_ = true;
        minute_start_ms_ = now_ms;
        return;
    }
    while (now_ms - minute_start_ms_ >= 60000u) {
        minute_start_ms_ += 60000u;
        cur_ = (cur_ + 1) % 60;
        bucket_[cur_] = 0.0f;
        if (minutes_ < 60u) ++minutes_;
    }
}

float AirtimeBudget::used_s() const {
    float s = 0.0f;
    for (float b : bucket_) s += b;
    s += kBackground * 3600.0f;                                           // the radio's own packets, a whole hour's worth
    s += assumed_s_ * std::fmax(0.0f, 1.0f - static_cast<float>(minutes_) / 60.0f);   // what may have come before
    return s;
}

int AirtimeBudget::level() const {
    const float u = used_s();
    if (u >= kHardS) return 2;
    if (u >= kSoftS) return 1;
    return 0;
}

}  // namespace kestrel::tlm
