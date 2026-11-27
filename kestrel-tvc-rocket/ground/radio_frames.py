#!/usr/bin/env python3
"""KESTREL radio frames in Python: encode / decode the flight computer's telemetry (firmware/core telemetry.hpp).

    python3 ground/radio_frames.py decode capture.bin [-o flight.csv]   raw bytes saved from the ground radio -> log CSV
    python3 ground/radio_frames.py demo out.bin                         the built-in simulated flight as radio bytes

The frames are MAVLink v1 shaped (0xFE, len, seq, sys, comp, msgid, payload, CRC-16/MCRF4XX + extra byte); the CRC is
checked against pymavlink's HEARTBEAT and RADIO_STATUS frames in firmware/core/tests and ground/test_radio.mjs.
"""
import struct
import sys

STX, SYS = 0xFE, 75
FAST, SLOW, HB, RS = 230, 231, 0, 109
EXTRA = {HB: 50, RS: 185, FAST: 0x4B, SLOW: 0x53}
FAST_FMT = "<IBB3h3hfhhhh3h4bh"        # 42 bytes
SLOW_FMT = "<IiihBBfHHHHHBBhHBBHIBB"   # 46 bytes
RS_FMT = "<HHBBBBB"                    # 9 bytes
COLS = ["t_ms", "state", "flags", "gx_dps", "gy_dps", "gz_dps", "ax", "ay", "az", "alt_m", "vz_ms", "baro_alt_m", "tilt_deg",
        "gimbal_y", "gimbal_z", "vbat", "lat", "lon", "gps_alt", "sats", "qx", "qy", "qz", "tab1", "tab2", "tab3", "tab4", "roll_deg", "rssi"]
assert struct.calcsize(FAST_FMT) == 42 and struct.calcsize(SLOW_FMT) == 46 and struct.calcsize(RS_FMT) == 9


def crc_x25(data, crc=0xFFFF):
    for b in data:
        t = (b ^ (crc & 0xFF)) & 0xFF
        t = (t ^ (t << 4)) & 0xFF
        crc = ((crc >> 8) ^ (t << 8) ^ (t << 3) ^ (t >> 4)) & 0xFFFF
    return crc


def encode(msgid, seq, payload, sys_id=SYS, comp=1):
    head = bytes([len(payload), seq & 255, sys_id, comp, msgid]) + bytes(payload)
    c = crc_x25(bytes([EXTRA[msgid]]), crc_x25(head))
    return bytes([STX]) + head + bytes([c & 255, c >> 8])


class Decoder:
    """sliding window, as the firmware's and the page's: a bad candidate costs only itself"""

    def __init__(self):
        self.w = bytearray()
        self.good = self.bad = 0

    def feed(self, data):
        out = []
        for b in data:
            self.w.append(b)
            while True:
                k = self.w.find(STX)
                if k < 0:
                    self.w.clear()
                    break
                del self.w[:k]
                if len(self.w) < 2:
                    break
                n = self.w[1]
                if n > 64:
                    self.bad += 1
                    del self.w[:1]
                    continue
                if len(self.w) < n + 8:
                    break
                mid = self.w[5]
                if mid in EXTRA and crc_x25(bytes([EXTRA[mid]]), crc_x25(self.w[1:6 + n])) == self.w[6 + n] | (self.w[7 + n] << 8):
                    out.append(dict(msgid=mid, seq=self.w[2], sys=self.w[3], comp=self.w[4], payload=bytes(self.w[6:6 + n])))
                    self.good += 1
                    del self.w[:n + 8]
                    continue
                self.bad += 1
                del self.w[:1]
        return out


def fast(p):
    v = struct.unpack(FAST_FMT, p)
    return dict(t=v[0], state=v[1], flags=v[2], g=v[3:6], a=v[6:9], alt=v[9], vz=v[10], tilt=v[11], gy=v[12], gz=v[13], q=v[14:17],
                tabs=v[17:21], roll=v[21])


def slow(p):
    v = struct.unpack(SLOW_FMT, p)
    keys = ["t", "lat_e7", "lon_e7", "gps_alt", "sats", "gps_valid", "baro", "vbat_mv", "cell1_mv", "servo_mv", "flight_no", "fw", "motor",
            "status", "apogee_dm", "airtime_ds", "rssi_local", "rssi_remote", "log_dropped", "log_records", "deploy_reason", "ground_heard"]
    return dict(zip(keys, v))


def row(f, s):
    lat = s["lat_e7"] / 1e7 if s and s["gps_valid"] else 0.0
    lon = s["lon_e7"] / 1e7 if s and s["gps_valid"] else 0.0
    return [f["t"], f["state"], f["flags"], *(x / 100 for x in f["g"]), *(x / 100 for x in f["a"]), f["alt"], f["vz"] / 100,
            s["baro"] if s else f["alt"], f["tilt"] / 100, f["gy"] / 100, f["gz"] / 100, s["vbat_mv"] / 1000 if s else 0.0, lat, lon,
            s["gps_alt"] if s else 0, s["sats"] if s else 0, *(x / 32767 for x in f["q"]), *(x / 4 for x in f["tabs"]), f["roll"] / 100,
            s["rssi_local"] if s else 0]


def decode_capture(data):
    """raw radio bytes -> (sessions {flight_no: [rows]}, stats)"""
    d = Decoder()
    flights, s, last_seq, lost, n = {}, None, None, 0, 0
    for fr in d.feed(data):
        if fr["sys"] != SYS:
            continue
        if last_seq is not None:
            gap = (fr["seq"] - last_seq - 1) & 255
            if gap < 128:
                lost += gap
        last_seq = fr["seq"]
        n += 1
        if fr["msgid"] == SLOW and len(fr["payload"]) == 46:
            s = slow(fr["payload"])
        elif fr["msgid"] == FAST and len(fr["payload"]) == 42:
            flights.setdefault(s["flight_no"] if s else 0, []).append(row(fast(fr["payload"]), s))
    return flights, dict(frames=n, lost=lost, bad=d.bad)


def write_csv(path, flights):
    with open(path, "w") as fh:
        fh.write(",".join(COLS) + "\n")
        for no, rows in flights.items():
            fh.write(f"# session: radio flight {no}\n")
            for r in rows:
                fh.write(",".join(f"{x:.7f}" if i in (16, 17) else (str(int(x)) if i in (0, 1, 2, 18, 19, 28) else f"{x:.4f}" if i in (20, 21, 22) else f"{x:.2f}")
                                  for i, x in enumerate(r)) + "\n")
            fh.write(f"# end: {len(rows)} records, 0 failed CRC\n")


def demo_bytes(csv_path):
    """the simulated flight as the radio would carry it (firmware rates: 50 + 5 Hz in flight, 1 + 0.5 Hz on the pad)"""
    rows = []
    for line in open(csv_path):
        if line[0].isdigit():
            rows.append([float(x) for x in line.strip().split(",")[:28]])
    out, seq = bytearray(), 0
    t0, t1 = rows[0][0], rows[-1][0]
    j, t, k, landed = 0, t0, 0, None
    while t <= t1:
        while j < len(rows) - 2 and rows[j + 1][0] <= t:
            j += 1
        a, b = rows[j], rows[j + 1]
        f = min(1.0, max(0.0, (t - a[0]) / max(1.0, b[0] - a[0])))
        r = [a[i] if i in (1, 2, 19) else a[i] + (b[i] - a[i]) * f for i in range(28)]
        st = int(r[1])
        if st == 6 and landed is None:
            landed = t
        fhz, shz = (50, 5) if 3 <= st <= 5 else (1, 0.5) if st == 2 else (0, 1 if landed is None or t - landed < 60000 else 0.2) if st == 6 else (0, 1)
        if fhz and k % round(500 / fhz) == 0:
            p = struct.pack(FAST_FMT, int(t), st, int(r[2]), *(round(x * 100) for x in r[3:6]), *(round(x * 100) for x in r[6:9]), r[9],
                            round(r[10] * 100), round(r[12] * 100), round(r[13] * 100), round(r[14] * 100), *(round(x * 32767) for x in r[20:23]),
                            *(round(x * 4) for x in r[23:27]), round(r[27] * 100))
            out += encode(FAST, seq, p)
            seq += 1
        if shz and k % round(500 / shz) == 3:
            p = struct.pack(SLOW_FMT, int(t), round(r[16] * 1e7), round(r[17] * 1e7), round(r[18]), int(r[19]), 1, r[11], round(r[15] * 1000), 0, 5000,
                            1, 300, 5, 207, 0, 1320, 150, 140, 0, 0, 0, 1)
            out += encode(SLOW, seq, p)
            seq += 1
        k += 1
        t += 2
    return bytes(out)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "decode":
        fl, st = decode_capture(open(sys.argv[2], "rb").read())
        out = sys.argv[4] if len(sys.argv) >= 5 and sys.argv[3] == "-o" else sys.argv[2].rsplit(".", 1)[0] + ".csv"
        write_csv(out, fl)
        print(f"{st['frames']} frames, {st['lost']} lost, {st['bad']} rejected -> {out}")
    elif len(sys.argv) >= 3 and sys.argv[1] == "demo":
        import os
        b = demo_bytes(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_flight.csv"))
        open(sys.argv[2], "wb").write(b)
        print(f"{len(b)} bytes -> {sys.argv[2]}")
    else:
        print(__doc__)
