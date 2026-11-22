#include "nmea.hpp"

#include <cstdlib>
#include <cstring>

namespace kestrel {

namespace {
int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}
}  // namespace

double nmea_to_degrees(const char* f, char hemi) {
    if (!f || !*f) return 0.0;
    const double v = std::atof(f);
    const int deg = static_cast<int>(v / 100.0);
    double d = deg + (v - deg * 100.0) / 60.0;
    if (hemi == 'S' || hemi == 'W') d = -d;
    return d;
}

size_t NmeaParser::make_sentence(const char* body, char* out, size_t out_len) {
    const size_t n = std::strlen(body);
    if (n + 7 > out_len) return 0;
    uint8_t cs = 0;
    for (size_t i = 0; i < n; ++i) cs ^= static_cast<uint8_t>(body[i]);
    static const char* hex = "0123456789ABCDEF";
    out[0] = '$';
    std::memcpy(out + 1, body, n);
    out[n + 1] = '*';
    out[n + 2] = hex[cs >> 4];
    out[n + 3] = hex[cs & 0xF];
    out[n + 4] = '\r';
    out[n + 5] = '\n';
    out[n + 6] = '\0';
    return n + 6;
}

bool NmeaParser::feed(char c) {
    if (c == '$') {
        in_sentence_ = true;
        len_ = 0;
        return false;
    }
    if (!in_sentence_) return false;
    if (c == '\r' || c == '\n') {
        in_sentence_ = false;
        buf_[len_] = '\0';
        return finish();
    }
    if (len_ >= sizeof(buf_) - 1) {   // overlong: drop
        in_sentence_ = false;
        return false;
    }
    buf_[len_++] = c;
    return false;
}

bool NmeaParser::finish() {
    char* star = std::strchr(buf_, '*');
    if (!star || star[1] == '\0' || star[2] == '\0') { ++bad_; return false; }
    uint8_t cs = 0;
    for (char* p = buf_; p < star; ++p) cs ^= static_cast<uint8_t>(*p);
    const int h = hexval(star[1]), l = hexval(star[2]);
    if (h < 0 || l < 0 || cs != static_cast<uint8_t>(h * 16 + l)) { ++bad_; return false; }
    *star = '\0';
    ++good_;
    // split on commas in place (empty fields preserved)
    char* f[24];
    int n = 0;
    char* p = buf_;
    f[n++] = p;
    while (*p && n < 24) {
        if (*p == ',') { *p = '\0'; f[n++] = p + 1; }
        ++p;
    }
    if (std::strlen(f[0]) < 5) return false;
    const char* type = f[0] + 2;   // skip talker (GP, GN, BD, GB, ...)
    if (std::strcmp(type, "GGA") == 0) return parse_gga(f, n);
    if (std::strcmp(type, "RMC") == 0) parse_rmc(f, n);
    return false;
}

bool NmeaParser::parse_gga(char** f, int n) {
    // $xxGGA,hhmmss.ss,lat,N,lon,E,quality,sats,hdop,alt,M,geoid,M,age,station
    if (n < 10) return false;
    fix_.utc_hhmmss = static_cast<uint32_t>(std::atof(f[1]));
    fix_.quality = static_cast<uint8_t>(std::atoi(f[6]));
    fix_.sats = static_cast<uint8_t>(std::atoi(f[7]));
    fix_.hdop = *f[8] ? static_cast<float>(std::atof(f[8])) : 99.9f;
    if (fix_.quality > 0 && *f[2] && *f[4]) {
        fix_.lat_deg = nmea_to_degrees(f[2], f[3][0]);
        fix_.lon_deg = nmea_to_degrees(f[4], f[5][0]);
        fix_.alt_m = static_cast<float>(std::atof(f[9]));
        fix_.valid = true;
    } else {
        fix_.valid = false;
    }
    return true;
}

bool NmeaParser::parse_rmc(char** f, int n) {
    // $xxRMC,hhmmss.ss,A,lat,N,lon,E,speed_kn,course,ddmmyy,...
    if (n < 8) return false;
    if (f[2][0] == 'A' && *f[7]) fix_.speed_mps = static_cast<float>(std::atof(f[7]) * 0.514444);
    return true;
}

}  // namespace kestrel
