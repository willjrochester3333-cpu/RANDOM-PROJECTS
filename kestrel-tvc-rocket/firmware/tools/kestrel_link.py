#!/usr/bin/env python3
"""KESTREL FC ground tool: talk to the flight computer over USB, download and plot flight logs.

    pip install pyserial matplotlib
    python kestrel_link.py ports                      # list serial ports (the Pico shows up as a USB serial device)
    python kestrel_link.py shell  --port COM5         # interactive command line (type 'help')
    python kestrel_link.py dump   --port COM5 -o flight.csv
    python kestrel_link.py plot   flight.csv          # altitude, velocity, attitude/TVC, battery, GPS track
    python kestrel_link.py summary flight.csv

Any serial terminal works too (115200 8N1, the speed is ignored by USB): type 'status', 'dump', ...
"""
import argparse
import csv
import sys
import threading
import time

STATES = ["BOOT", "CALIBRATING", "READY", "BOOST", "COAST", "DESCENT", "LANDED", "ERROR"]


def open_port(port):
    import serial
    s = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(0.2)
    s.reset_input_buffer()
    return s


def cmd_ports(_):
    from serial.tools import list_ports
    for p in list_ports.comports():
        tag = "  <- Raspberry Pi" if (p.vid == 0x2E8A) else ""
        print(f"{p.device:15s} {p.description}{tag}")


def cmd_shell(a):
    s = open_port(a.port)
    stop = False

    def reader():
        while not stop:
            data = s.read(256)
            if data:
                sys.stdout.write(data.decode(errors="replace"))
                sys.stdout.flush()
    threading.Thread(target=reader, daemon=True).start()
    print("connected - type commands, Ctrl+C to quit")
    try:
        while True:
            line = input()
            s.write((line + "\r").encode())
    except (KeyboardInterrupt, EOFError):
        stop = True


def cmd_dump(a):
    s = open_port(a.port)
    s.write(b"\rdump\r")
    rows, started, t_last = [], False, time.time()
    with open(a.output, "w", newline="") as fh:
        while time.time() - t_last < 10:
            line = s.readline().decode(errors="replace").strip()
            if not line:
                continue
            t_last = time.time()
            if line.startswith("t_ms,"):
                started = True
            if not started:
                continue
            if line.startswith("# end"):
                print(line)
                break
            fh.write(line + "\n")
            if not line.startswith("#") and not line.startswith("t_ms"):
                rows.append(line)
                if len(rows) % 5000 == 0:
                    print(f"  {len(rows)} records...")
    print(f"wrote {len(rows)} records to {a.output}")


def load(path):
    flights, cur = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("# session"):
                cur = {"header": line.strip(), "rows": []}
                flights.append(cur)
                continue
            if line.startswith("#") or line.startswith("t_ms"):
                continue
            if cur is None:
                cur = {"header": "# session: ?", "rows": []}
                flights.append(cur)
            v = line.strip().split(",")
            if len(v) < 23:
                continue
            keys = ["t_ms", "state", "flags", "gx", "gy", "gz", "ax", "ay", "az", "alt", "vz", "baro_alt", "tilt",
                    "gimbal_y", "gimbal_z", "vbat", "lat", "lon", "gps_alt", "sats", "qx", "qy", "qz",
                    "tab1", "tab2", "tab3", "tab4", "roll"]          # KESTREL-2 (fw 2.00) adds the fin tabs + roll
            row = {k: float(x) for k, x in zip(keys, v)}
            for k in keys[23:]:
                row.setdefault(k, 0.0)
            cur["rows"].append(row)
    return [f for f in flights if f["rows"]]


def flight_of_interest(flights):
    """The last session that actually launched (has BOOST samples), else the last session."""
    for f in reversed(flights):
        if any(r["state"] == 3 for r in f["rows"]):
            return f
    return flights[-1]


def cmd_summary(a):
    flights = load(a.csv)
    for f in flights:
        rows = f["rows"]
        launched = [r for r in rows if r["state"] == 3]
        line = f"{f['header']}: {len(rows)} records"
        if launched:
            t0 = launched[0]["t_ms"]
            apo = max(rows, key=lambda r: r["alt"])
            dep = next((r for r in rows if int(r["flags"]) & 2), None)
            line += (f", apogee {apo['alt']:.1f} m at T+{(apo['t_ms'] - t0) / 1000:.2f} s, max tilt in boost "
                     f"{max(r['tilt'] for r in launched):.1f} deg")
            if dep:
                line += f", deploy at T+{(dep['t_ms'] - t0) / 1000:.2f} s ({dep['alt']:.1f} m)"
            gps = [r for r in rows if int(r["flags"]) & 8]
            if gps:
                line += f", last GPS {gps[-1]['lat']:.6f},{gps[-1]['lon']:.6f}"
        print(line)


def cmd_plot(a):
    import matplotlib.pyplot as plt
    f = flight_of_interest(load(a.csv))
    rows = f["rows"]
    boost = [r for r in rows if r["state"] == 3]
    t0 = boost[0]["t_ms"] if boost else rows[0]["t_ms"]
    t = [(r["t_ms"] - t0) / 1000 for r in rows]
    fig, ax = plt.subplots(3, 2, figsize=(13, 10.5))
    fig.suptitle(f"KESTREL flight log - {f['header'].lstrip('# ')}")
    a0 = ax[0][0]
    a0.plot(t, [r["alt"] for r in rows], color="#2a78d6", label="filtered (baro + accel)")
    a0.plot(t, [r["baro_alt"] for r in rows], color="#eb6834", lw=0.8, alpha=0.8, label="raw barometer")
    a0.set_title("Altitude above pad (m)", loc="left"); a0.legend(loc="upper right"); a0.grid(alpha=0.3)
    a1 = ax[0][1]
    a1.plot(t, [r["vz"] for r in rows], color="#2a78d6")
    a1.axhline(0, color="#52514e", lw=0.8)
    a1.set_title("Vertical speed (m/s)", loc="left"); a1.grid(alpha=0.3)
    a2 = ax[1][0]
    a2.plot(t, [r["tilt"] for r in rows], color="#2a78d6", label="tilt from target")
    a2.plot(t, [r["gimbal_y"] for r in rows], color="#eb6834", lw=0.8, label="gimbal y")
    a2.plot(t, [r["gimbal_z"] for r in rows], color="#1baf7a", lw=0.8, label="gimbal z")
    a2.set_xlim(-0.5, (boost[-1]["t_ms"] - t0) / 1000 + 2 if boost else None)
    a2.set_title("Attitude and thrust vectoring (deg)", loc="left"); a2.legend(); a2.grid(alpha=0.3)
    a3 = ax[1][1]
    for k, c in enumerate(("#2a78d6", "#eb6834", "#1baf7a", "#eda100")):
        a3.plot(t, [r[f"tab{k + 1}"] for r in rows], color=c, lw=0.9, label=f"tab {k + 1}")
    a3.plot(t, [r["gx"] / 10.0 for r in rows], color="#52514e", lw=0.8, ls="--", label="roll rate / 10 (deg/s)")
    a3.set_xlim(-0.5, (boost[-1]["t_ms"] - t0) / 1000 + 6 if boost else None)
    a3.set_title("Fin tabs (deg) and roll rate", loc="left"); a3.legend(ncol=2, fontsize=8); a3.grid(alpha=0.3)
    a4 = ax[2][0]
    a4.plot(t, [r["state"] for r in rows], color="#52514e", drawstyle="steps-post")
    a4.set_yticks(range(len(STATES))); a4.set_yticklabels(STATES); a4.grid(alpha=0.3)
    a4.set_title(f"Flight state (battery {min(r['vbat'] for r in rows):.2f}-{max(r['vbat'] for r in rows):.2f} V)", loc="left")
    for axx in (a0, a1, a2, a3, a4):
        axx.set_xlabel("time since launch (s)")
    a5 = ax[2][1]
    g = [r for r in rows if int(r["flags"]) & 8 and r["lat"] != 0]
    if g:
        a5.plot([r["lon"] for r in g], [r["lat"] for r in g], color="#2a78d6", marker=".", ms=3)
        a5.plot(g[0]["lon"], g[0]["lat"], "o", color="#1baf7a", label="first fix")
        a5.plot(g[-1]["lon"], g[-1]["lat"], "s", color="#eb6834", label="landing")
        a5.set_title(f"GPS track - landing {g[-1]['lat']:.6f}, {g[-1]['lon']:.6f}", loc="left")
        a5.legend()
    else:
        a5.text(0.5, 0.5, "no GPS fix in this log", ha="center", transform=a5.transAxes)
    a5.ticklabel_format(useOffset=False)
    a5.set_xlabel("longitude"); a5.set_ylabel("latitude"); a5.grid(alpha=0.3)
    fig.tight_layout()
    out = a.csv.rsplit(".", 1)[0] + ".png"
    fig.savefig(out, dpi=130)
    print("saved", out)
    if not a.no_show:
        plt.show()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ports")
    s = sub.add_parser("shell"); s.add_argument("--port", required=True)
    d = sub.add_parser("dump"); d.add_argument("--port", required=True); d.add_argument("-o", "--output", default="flight.csv")
    pl = sub.add_parser("plot"); pl.add_argument("csv"); pl.add_argument("--no-show", action="store_true")
    su = sub.add_parser("summary"); su.add_argument("csv")
    a = p.parse_args()
    {"ports": cmd_ports, "shell": cmd_shell, "dump": cmd_dump, "plot": cmd_plot, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
