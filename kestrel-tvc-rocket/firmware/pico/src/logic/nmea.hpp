// Minimal, allocation-free NMEA 0183 parser for the ATGM336H (GPS + BeiDou) module.
// Understands GGA (position, altitude, satellites) and RMC (validity, ground speed); checks checksums.
// Platform independent: unit-tested on the host (firmware/pico/tests).
#pragma once
#include <cstddef>
#include <cstdint>

namespace kestrel {

struct NmeaFix {
    bool valid{false};
    double lat_deg{0}, lon_deg{0};
    float alt_m{0};        // above mean sea level
    float hdop{99.9f};
    uint8_t sats{0};
    uint8_t quality{0};    // GGA fix quality (0 none, 1 GPS, 2 DGPS, ...)
    uint32_t utc_hhmmss{0};
    float speed_mps{0};    // from RMC
};

class NmeaParser {
public:
    // Feed one received byte. Returns true when a complete, checksum-valid GGA sentence was parsed.
    bool feed(char c);
    const NmeaFix& fix() const { return fix_; }
    uint32_t good_sentences() const { return good_; }
    uint32_t bad_checksums() const { return bad_; }

    // Build "$<body>*CS\r\n" into out (returns length, 0 if it does not fit). body excludes '$' and '*'.
    static size_t make_sentence(const char* body, char* out, size_t out_len);

private:
    bool finish();
    bool parse_gga(char** f, int n);
    bool parse_rmc(char** f, int n);

    char buf_[100]{};
    size_t len_{0};
    bool in_sentence_{false};
    NmeaFix fix_{};
    uint32_t good_{0}, bad_{0};
};

// ddmm.mmmm + hemisphere -> signed decimal degrees (helper, exposed for tests)
double nmea_to_degrees(const char* field, char hemisphere);

}  // namespace kestrel
