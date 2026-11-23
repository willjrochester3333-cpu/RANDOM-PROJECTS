"""Compose the KESTREL-2 flight video: two camera views on top, live telemetry bottom-left, live graphs
bottom-right. Static chart chrome is drawn once with matplotlib; per frame the curves are drawn with PIL at 2x
and downsampled (fast and smooth). Dark theme, categorical colours from the validated palette (dark steps)."""
import math
import os
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
VIEW_W, VIEW_H = 960, 540
TEL_W = 560
BG = "#121211"
SURF = "#1a1a19"
INK = "#f0efec"
INK2 = "#c3c2b7"
MUTED = "#8b8a83"
GRID = "#2c2c2a"
S = ["#3987e5", "#d95926", "#199e70", "#c98500"]          # palette slots 1-4, dark-surface steps
PHASE = {3: ("BOOST", "#3a2418"), 4: ("COAST", "#17283a"), 5: ("DESCENT", "#15302a"), 6: ("LANDED", "#262624")}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONOB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def f(path, size):
    return ImageFont.truetype(path, size)


def phase_name(st):
    return {0: "PAD", 1: "PAD", 2: "PAD - ARMED", 3: "BOOST", 4: "COAST", 5: "DESCENT", 6: "LANDED", 7: "ERROR"}.get(st, "?")


# ---------------------------------------------------------------------------------------------- graphs
class Graphs:
    """2 x 2 live charts; static chrome rendered once with matplotlib, curves drawn per frame."""
    PANELS = [
        ("Altitude (m)", [("altitude", "z", 0), ("flight-computer estimate", "alt_est", 1)]),
        ("Vertical speed (m/s)", [("vertical speed", "vz", 0)]),
        ("Attitude and thrust vector (deg)", [("tilt", "tilt", 0), ("roll angle", "roll", 1), ("gimbal y", "gy", 2), ("gimbal z", "gz", 3)]),
        ("Fin control tabs (deg)", [("tab 1", "tab0", 0), ("tab 2", "tab1", 1), ("tab 3", "tab2", 2), ("tab 4", "tab3", 3)]),
    ]

    def __init__(self, frames, size):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        self.sz = size
        self.t = np.array([fr["t"] for fr in frames])
        cols = {"z": [fr["z"] for fr in frames], "alt_est": [fr["alt_est"] for fr in frames], "vz": [fr["vz"] for fr in frames],
                "tilt": [fr["tilt"] for fr in frames], "roll": [fr["roll"] for fr in frames], "gy": [fr["gy"] for fr in frames],
                "gz": [fr["gz"] for fr in frames]}
        for k in range(4):
            cols[f"tab{k}"] = [fr["tabs"][k] for fr in frames]
        self.cols = {k: np.array(v) for k, v in cols.items()}
        # the flight computer's estimate is meaningless before arming; hide it until lift-off
        self.cols["alt_est"] = np.where(self.t < 0, np.nan, self.cols["alt_est"])
        self.state = np.array([fr["state"] for fr in frames])
        self.sep = np.array([fr["sep"] for fr in frames])
        for k in ("tilt", "roll", "gy", "gz", "tab0", "tab1", "tab2", "tab3"):     # attitude meaningless under the chute
            self.cols[k] = np.where(self.sep, np.nan, self.cols[k])
        sc = 2
        fig = plt.figure(figsize=(size[0] * sc / 100, size[1] * sc / 100), dpi=100, facecolor="none")
        self.axes = []
        t0, t1 = self.t[0], self.t[-1]
        boxes = [(0.06, 0.58, 0.42, 0.33), (0.565, 0.58, 0.42, 0.33), (0.06, 0.10, 0.42, 0.33), (0.565, 0.10, 0.42, 0.33)]
        self.ylims = []
        for (title, series), box in zip(self.PANELS, boxes):
            ax = fig.add_axes(box, facecolor="none")
            vals = np.concatenate([self.cols[c][np.isfinite(self.cols[c])] for _, c, _ in series])
            lo, hi = float(np.min(vals)), float(np.max(vals))
            if title.startswith("Fin"):
                lo, hi = -16.0, 16.0
            elif title.startswith("Attitude"):
                m = max(5.0, abs(lo), abs(hi)) * 1.15
                lo, hi = -m, m
            else:
                pad = 0.08 * (hi - lo + 1e-6)
                lo, hi = lo - pad, hi + pad
            ax.set_xlim(t0, t1)
            ax.set_ylim(lo, hi)
            self.ylims.append((lo, hi))
            ax.grid(True, color=GRID, lw=1.2 * sc / 2)
            for s_ in ("top", "right"):
                ax.spines[s_].set_visible(False)
            for s_ in ("left", "bottom"):
                ax.spines[s_].set_color(MUTED)
            ax.tick_params(colors=INK2, labelsize=9 * sc)
            ax.set_title(title, loc="left", color=INK, fontsize=11 * sc, pad=8 * sc)
            ax.axhline(0, color=MUTED, lw=0.8 * sc)
            if box[1] < 0.5:
                ax.set_xlabel("time since ignition (s)", color=INK2, fontsize=9 * sc)
            # legend (always present for >= 2 series; colour never carries identity alone - names on the legend)
            if len(series) > 1:
                for j, (name, _, ci) in enumerate(series):
                    ax.plot([], [], color=S[ci], lw=2 * sc, label=name)
                ax.legend(loc="upper left", fontsize=8.5 * sc, frameon=False, labelcolor=INK2, ncol=2 if len(series) > 2 else 1,
                          handlelength=1.4)
            self.axes.append(ax)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())
        self.chrome = Image.fromarray(buf.copy(), "RGBA")
        self.H2 = buf.shape[0]
        # data -> pixel transforms (matplotlib: origin bottom-left; PIL: top-left)
        self.tx = []
        for ax in self.axes:
            bb = ax.get_window_extent()
            self.tx.append((bb.x0, bb.y0, bb.width, bb.height, ax.get_xlim(), ax.get_ylim()))
        plt.close(fig)
        self.fonts = (f(FONT, 11 * sc), f(MONO, 11 * sc))

    def _px(self, i, x, y):
        x0, y0, w, h, (a0, a1), (b0, b1) = self.tx[i]
        px = x0 + (x - a0) / (a1 - a0) * w
        py = self.H2 - (y0 + (y - b0) / (b1 - b0) * h)
        return px, py

    def draw(self, k):
        im = Image.new("RGB", self.chrome.size, SURF)
        d = ImageDraw.Draw(im)
        tnow = self.t[k]
        sc = 2
        for i, (title, series) in enumerate(self.PANELS):
            x0, y0, w, h, (a0, a1), (b0, b1) = self.tx[i]
            # phase bands up to now
            for code, (name, col) in PHASE.items():
                m = (self.state[: k + 1] == code)
                if m.any():
                    ta, tb = self.t[: k + 1][m][0], self.t[: k + 1][m][-1]
                    xa, _ = self._px(i, ta, b0)
                    xb, _ = self._px(i, tb, b0)
                    d.rectangle([xa, self.H2 - (y0 + h), xb, self.H2 - y0], fill=col)
        im.paste(self.chrome, (0, 0), self.chrome)                 # grid, axes, titles, legends over the bands
        d = ImageDraw.Draw(im)
        for i, (title, series) in enumerate(self.PANELS):
            x0, y0, w, h, (a0, a1), (b0, b1) = self.tx[i]
            for name, c, ci in series:
                y = self.cols[c][: k + 1]
                tt = self.t[: k + 1]
                ok = np.isfinite(y)
                if ok.sum() < 2:
                    continue
                pts = [self._px(i, a, b) for a, b in zip(tt[ok], y[ok])]
                d.line(pts, fill=S[ci], width=3 * sc if c != "alt_est" else 2 * sc, joint="curve")
                ex, ey = pts[-1]
                rr = 5 * sc
                d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=S[ci], outline=SURF, width=2 * sc)
            xn, _ = self._px(i, tnow, b0)                                # "now" cursor
            d.line([(xn, self.H2 - y0), (xn, self.H2 - (y0 + h))], fill=MUTED, width=sc)
        return im.resize(self.sz, Image.LANCZOS)


# ---------------------------------------------------------------------------------------------- telemetry
def telemetry(fr, meta, maxalt, events, size):
    im = Image.new("RGB", size, SURF)
    d = ImageDraw.Draw(im)
    x = 26
    d.text((x, 18), "KESTREL-2", font=f(FONTB, 30), fill=INK)
    d.text((x + 205, 28), f"simulated flight #{meta['seed']}", font=f(FONT, 17), fill=INK2)
    t = fr["t"]
    tt = f"T{'+' if t >= 0 else '-'} {abs(t):05.2f} s"
    d.text((x, 62), tt, font=f(MONOB, 40), fill=INK)
    ph = phase_name(fr["state"])
    if fr["sep"] and fr["state"] < 5:
        ph = "DESCENT"
    pcol = {"BOOST": "#d95926", "COAST": "#3987e5", "DESCENT": "#199e70", "LANDED": INK2}.get(ph, INK2)
    d.rounded_rectangle([x + 300, 70, x + 300 + 200, 106], radius=8, outline=pcol, width=2)
    d.text((x + 400, 88), ph, font=f(FONTB, 19), fill=INK, anchor="mm")
    rows = [
        ("Altitude", f"{fr['z']:6.1f} m", f"computer {fr['alt_est']:6.1f} m" if t >= 0 else ""),
        ("Vertical speed", f"{fr['vz']:+6.1f} m/s", f"speed {fr['speed']:5.1f} m/s"),
        ("Acceleration", f"{fr['accel_g']:5.1f} g", f"thrust {fr['thrust']:5.1f} N"),
        ("Tilt / roll", f"{fr['tilt']:5.1f}°" if not fr["sep"] else "  --", f"roll {fr['roll']:+5.0f}°  {fr['p']:+5.0f}°/s" if not fr["sep"] else ""),
        ("TVC gimbal", f"{fr['gy']:+4.1f}° {fr['gz']:+4.1f}°" if not fr["sep"] else "centred", "y / z  (limit 6°)"),
        ("Fin tabs", " ".join(f"{v:+4.1f}" for v in fr["tabs"]) if not fr["sep"] else "centred",
         "1-4 (limit 15°)" if not fr["sep"] else "steering off under the parachute"),
        ("Mass", f"{fr['mass'] * 1000:5.0f} g", f"q {fr['qdyn']:5.0f} Pa"),
        ("Max altitude", f"{maxalt:6.1f} m", ""),
    ]
    y = 122
    for name, val, extra in rows:
        d.text((x, y), name, font=f(FONT, 17), fill=INK2)
        d.text((x + 165, y - 2), val, font=f(MONOB, 21), fill=INK)
        if extra:
            d.text((x + 165, y + 23), extra, font=f(MONO, 14), fill=MUTED)
        y += 44
    # parachute line
    if not fr["sep"]:
        chute = "parachute stowed"
    elif fr["chute"] < 1:
        chute = f"parachute OUT - opening {fr['chute'] * 100:3.0f} %"
    else:
        chute = "parachute open"
    ev = events
    dep = ev.get("deploy_cmd_t")
    if dep is not None and t >= dep:
        chute += f"   (released T+{dep:.2f} s, apogee T+{ev.get('apogee_t', 0):.2f} s)"
    d.text((x, y), chute, font=f(FONT, 15), fill=INK2)
    y += 24
    d.text((x, y), f"wind {meta['wind']:.1f} m/s towards {meta['wind_to']:.0f}°   payload {meta['payload_g']:.0f} g   motor {meta['motor']}",
           font=f(FONT, 14), fill=MUTED)
    return im


def caption(im, text, sub):
    d = ImageDraw.Draw(im, "RGBA")
    w = max(d.textlength(text, font=f(FONTB, 18)), d.textlength(sub, font=f(FONT, 14))) + 28
    d.rounded_rectangle([12, 12, 12 + w, 66], radius=8, fill=(18, 18, 17, 190))
    d.text((24, 18), text, font=f(FONTB, 18), fill=INK)
    d.text((24, 42), sub, font=f(FONT, 14), fill=INK2)


def compose_video(traj, view_dir, mp4, draft=False):
    frames, meta = traj["frames"], traj["meta"]
    out = os.path.join(view_dir, "frames")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    g = Graphs(frames, (W - TEL_W, H - VIEW_H))
    maxalt = 0.0
    poster_k = None
    for k, fr in enumerate(frames):
        maxalt = max(maxalt, fr["z"])
        canvas = Image.new("RGB", (W, H), BG)
        for j, (cam, title, sub) in enumerate((("ground", "GROUND CAMERA", "tracking camera, 30 m from the pad"),
                                               ("onboard", "ONBOARD CAMERA", "camera pod, looking down past the fins"))):
            p = os.path.join(view_dir, cam, f"{k + 1:04d}.png")
            if os.path.exists(p):
                v = Image.open(p).convert("RGB")
                if v.size != (VIEW_W, VIEW_H):
                    v = v.resize((VIEW_W, VIEW_H), Image.LANCZOS)
            else:
                v = Image.new("RGB", (VIEW_W, VIEW_H), "#202020")
            caption(v, title, sub)
            canvas.paste(v, (j * VIEW_W, 0))
        canvas.paste(telemetry(fr, meta, maxalt, meta["events"], (TEL_W, H - VIEW_H)), (0, VIEW_H))
        canvas.paste(g.draw(k), (TEL_W, VIEW_H))
        d = ImageDraw.Draw(canvas)
        d.line([(0, VIEW_H), (W, VIEW_H)], fill=GRID, width=2)
        d.line([(VIEW_W, 0), (VIEW_W, VIEW_H)], fill=GRID, width=2)
        d.line([(TEL_W, VIEW_H), (TEL_W, H)], fill=GRID, width=2)
        canvas.save(os.path.join(out, f"{k:05d}.png"), compress_level=1)
        if poster_k is None and fr["t"] >= 1.2:
            poster_k = k
    fps = meta["fps"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(out, "%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23" if draft else "19", "-preset", "medium",
                    "-movflags", "+faststart", mp4], check=True)
    if poster_k is not None:
        shutil.copy(os.path.join(out, f"{poster_k:05d}.png"), mp4.replace(".mp4", "_poster.png"))
    return mp4
