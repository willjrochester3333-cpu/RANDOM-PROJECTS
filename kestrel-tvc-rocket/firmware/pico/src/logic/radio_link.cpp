#include "radio_link.hpp"

#include <cstring>

namespace kestrel {

void RadioLink::set_enabled(bool on) {
    enabled_ = on;
    if (!on) head_ = tail_ = count_ = 0;
}

bool RadioLink::push_frame(uint8_t msgid, const void* payload, uint8_t len) {
    uint8_t buf[tlm::kMaxPayload + tlm::kOverhead];
    const size_t n = tlm::encode(msgid, seq_, payload, len, buf);
    if (n == 0 || kRing - count_ < n) {           // never send half a frame
        ++frames_dropped_;
        return false;
    }
    for (size_t i = 0; i < n; ++i) {
        ring_[head_] = buf[i];
        head_ = (head_ + 1) % kRing;
    }
    count_ += n;
    ++seq_;
    ++frames_sent_;
    budget_.add(tlm::frame_airtime_s(n));
    return true;
}

void RadioLink::step(uint32_t loop, uint32_t now_ms, FlightState st, float t_since_landed_s, const LogRecord& r,
                     const tlm::SlowPayload& slow) {
    budget_.tick(now_ms);
    if (!enabled_) { rates_ = {}; return; }
    const FlightState rate_state = testing(now_ms) ? FlightState::COAST : st;
    rates_ = tlm::rates_for(rate_state, t_since_landed_s, budget_.level());
    if (rates_.fast_div && loop % rates_.fast_div == 0) {
        const bool radio_full = have_radio_status(now_ms) && rs_.txbuf < kMinTxbufPct;
        if (radio_full) {
            ++frames_held_;                         // the radio cannot keep up (weak link): let it drain
        } else {
            tlm::FastPayload f;
            tlm::make_fast(r, f);
            push_frame(tlm::kMsgFast, &f, sizeof f);
        }
    }
    if (rates_.slow_div && loop % rates_.slow_div == 3) {      // offset so it never shares a loop with a fast frame
        tlm::SlowPayload s = slow;
        const float a = budget_.used_s() * 10.0f;
        s.airtime_ds = static_cast<uint16_t>(a > 65535.0f ? 65535.0f : a);
        s.rssi_local = have_radio_status(now_ms) ? rs_.rssi : 0;
        s.rssi_remote = have_radio_status(now_ms) ? rs_.remrssi : 0;
        s.ground_heard = ground_heard(now_ms) ? 1 : 0;
        push_frame(tlm::kMsgSlow, &s, sizeof s);
    }
    if (loop % kHeartbeatDiv == 7) {
        // MAVLink HEARTBEAT: custom_mode = flight state, type 9 (rocket), autopilot 8 (none), base_mode 0,
        // system_status 4 (active) in flight / 3 (standby) on the ground, mavlink_version 3
        const bool flying = st == FlightState::BOOST || st == FlightState::COAST || st == FlightState::DESCENT;
        uint8_t hb[9] = {static_cast<uint8_t>(st), 0, 0, 0, 9, 8, 0, static_cast<uint8_t>(flying ? 4 : 3), 3};
        push_frame(tlm::kMsgHeartbeat, hb, sizeof hb);
    }
}

size_t RadioLink::tx_pop(uint8_t* out, size_t max) {
    size_t n = 0;
    while (n < max && count_ > 0) {
        out[n++] = ring_[tail_];
        tail_ = (tail_ + 1) % kRing;
        --count_;
    }
    bytes_sent_ += static_cast<uint32_t>(n);
    return n;
}

void RadioLink::rx_byte(uint8_t b, uint32_t now_ms) {
    if (!dec_.feed(b)) return;
    if (dec_.msgid() == tlm::kMsgRadioStatus && dec_.len() == sizeof(tlm::RadioStatus)) {
        std::memcpy(&rs_, dec_.payload(), sizeof rs_);  // from our own radio (sys '3', comp 'D') or the ground radio's
        rs_ms_ = now_ms ? now_ms : 1;
    } else if (dec_.msgid() == tlm::kMsgHeartbeat && dec_.sysid() != tlm::kSysId) {
        gs_ms_ = now_ms ? now_ms : 1;               // Mission Control's heartbeat came through the link
    }
}

}  // namespace kestrel
