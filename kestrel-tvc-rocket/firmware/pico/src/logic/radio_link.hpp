// Telemetry scheduling and framing for the radio socket (SiK 433 MHz radio on UART1). Platform independent: the Pico
// application calls step() once per 500 Hz loop and moves bytes between this object and the UART; host-tested.
#pragma once
#include <cstddef>
#include <cstdint>

#include "kestrel/telemetry.hpp"
#include "kestrel/types.hpp"

namespace kestrel {

class RadioLink {
public:
    static constexpr size_t kRing = 2048;            // ~0.35 s at 57600 baud
    static constexpr uint32_t kHeartbeatDiv = 500;   // 1 Hz HEARTBEAT: makes our radio report RADIO_STATUS to us
    static constexpr uint8_t kMinTxbufPct = 25;      // radio's serial buffer nearly full -> skip motion frames
    static constexpr uint32_t kTestSeconds = 60;

    void set_enabled(bool on);
    bool enabled() const { return enabled_; }
    // Once per control loop. `slow` is filled by the caller except the link fields (airtime, RSSI, ground_heard).
    void step(uint32_t loop, uint32_t now_ms, FlightState st, float t_since_landed_s, const LogRecord& r,
              const tlm::SlowPayload& slow);
    void start_test(uint32_t now_ms) { test_until_ms_ = now_ms + kTestSeconds * 1000u; }
    bool testing(uint32_t now_ms) const { return static_cast<int32_t>(test_until_ms_ - now_ms) > 0; }

    // UART side
    size_t tx_pending() const { return count_; }
    size_t tx_pop(uint8_t* out, size_t max);
    void rx_byte(uint8_t b, uint32_t now_ms);

    // status
    bool have_radio_status(uint32_t now_ms) const { return rs_ms_ != 0 && now_ms - rs_ms_ < 5000u; }
    const tlm::RadioStatus& radio_status() const { return rs_; }
    bool ground_heard(uint32_t now_ms) const { return gs_ms_ != 0 && now_ms - gs_ms_ < 3000u; }
    uint32_t frames_sent() const { return frames_sent_; }
    uint32_t frames_dropped() const { return frames_dropped_; }
    uint32_t frames_held() const { return frames_held_; }
    uint32_t bytes_sent() const { return bytes_sent_; }
    uint32_t rx_good() const { return dec_.good(); }
    uint32_t rx_bad() const { return dec_.bad(); }
    float airtime_used_s() const { return budget_.used_s(); }
    int budget_level() const { return budget_.level(); }
    tlm::Rates rates() const { return rates_; }
    uint8_t rssi_for_log(uint32_t now_ms) const { return have_radio_status(now_ms) ? rs_.rssi : 0; }

private:
    bool push_frame(uint8_t msgid, const void* payload, uint8_t len);
    uint8_t ring_[kRing]{};
    size_t head_{0}, tail_{0}, count_{0};
    tlm::AirtimeBudget budget_{};
    tlm::Decoder dec_{};
    tlm::RadioStatus rs_{};
    uint32_t rs_ms_{0}, gs_ms_{0};
    uint32_t test_until_ms_{0};
    tlm::Rates rates_{};
    uint8_t seq_{0};
    bool enabled_{true};
    uint32_t frames_sent_{0}, frames_dropped_{0}, frames_held_{0}, bytes_sent_{0};
};

}  // namespace kestrel
