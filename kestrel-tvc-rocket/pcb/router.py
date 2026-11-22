#!/usr/bin/env python3
"""KESTREL FC grid router (A*, 2 signal layers + vias), with GND/+3V3 fan-out to inner planes.

    python3 router.py build/geometry.json build/routes.json

Design rules (JLCPCB 4-layer standard capability is 0.09/0.09 mm; we stay well above it):
  signal track 0.18 mm, power 0.5 / 0.8 mm, RF 0.36 mm (~50 ohm microstrip over In1 GND),
  clearance 0.13 mm, via 0.3 mm drill / 0.55 mm pad, copper-to-edge 0.3 mm.
Obstacle maps are "inflated" per track class so a centre-line path on a free cell is DRC-clean by construction.
"""
import heapq
import json
import math
import sys
import time

import numpy as np

G = 0.1                 # grid pitch (mm)
CLR = 0.13
EDGE = 0.30
VIA_D, VIA_DRILL = 0.55, 0.30
HOLE_CLR = 0.25
CLASSES = {"sig": 0.18, "pwr": 0.50, "hi": 0.80, "rf": 0.36}
NET_CLASS = {
    "VBAT_IN": "hi", "VBAT_RP": "hi", "VBAT_SW": "hi", "5V_SERVO": "hi", "SW_S": "hi",
    "5V_LOG": "pwr", "SW_L": "pwr", "VSYS": "pwr", "AUX_5V": "pwr", "+3V3_GPS": "pwr",
    "RF_ANT": "rf", "RF_IN": "rf",
}
PLANE_NETS = {"GND": "In1", "+3V3": "In2"}       # connected by fan-out vias, never routed
F_ONLY = {"RF_ANT", "RF_IN"}
VIA_COST = 60            # in grid units of 0.1 mm*10 (orthogonal step = 10)


class Board:
    def __init__(self, geo):
        self.W, self.H = geo["board"]
        self.nx = int(round(self.W / G)) + 1
        self.ny = int(round(self.H / G)) + 1
        self.pads = geo["pads"]
        self.holes = geo["holes"]
        self.net_names = sorted({p["net"] for p in self.pads if p["net"]})
        self.net_id = {n: i for i, n in enumerate(self.net_names)}
        xs = np.arange(self.nx) * G
        ys = np.arange(self.ny) * G
        self.X, self.Y = np.meshgrid(xs, ys)
        # owner grids: -1 free, -2 blocked for all, k = owned by net k
        self.grid = {c: [np.full((self.ny, self.nx), -1, np.int32) for _ in range(2)] for c in CLASSES}
        self.via = np.full((self.ny, self.nx), -1, np.int32)
        self.hole = np.zeros((self.ny, self.nx), bool)   # True = a via centre here would be too close to a drilled hole
        self.keepouts = geo.get("keepouts", [])
        self.tracks = []        # (net, layer, x0, y0, x1, y1, width)
        self.vias = []          # (net, x, y)
        self._static()

    # ---------------- rasterisation ----------------
    def _window(self, x0, y0, x1, y1):
        i0 = max(int(math.floor(x0 / G)), 0)
        i1 = min(int(math.ceil(x1 / G)) + 1, self.nx)
        j0 = max(int(math.floor(y0 / G)), 0)
        j1 = min(int(math.ceil(y1 / G)) + 1, self.ny)
        return j0, j1, i0, i1

    def _mark(self, grid, mask, j0, i0, owner):
        sub = grid[j0:j0 + mask.shape[0], i0:i0 + mask.shape[1]]
        if owner == -2:
            sub[mask] = -2
            return
        free = mask & (sub == -1)
        other = mask & (sub != -1) & (sub != owner)
        sub[free] = owner
        sub[other] = -2

    @staticmethod
    def _seg_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            return np.hypot(px - ax, py - ay)
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0.0, 1.0)
        return np.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def _poly_mask(self, poly, r, j0, j1, i0, i1):
        X = self.X[j0:j1, i0:i1]
        Y = self.Y[j0:j1, i0:i1]
        inside = np.zeros(X.shape, bool)
        dmin = np.full(X.shape, 1e9)
        n = len(poly)
        for k in range(n):
            ax, ay = poly[k]
            bx, by = poly[(k + 1) % n]
            cond = ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / ((by - ay) if by != ay else 1e-12) + ax)
            inside ^= cond
            dmin = np.minimum(dmin, self._seg_dist(X, Y, ax, ay, bx, by))
        return inside | (dmin <= r)

    def stamp_poly(self, polys, r, owner, grids):
        for poly in polys:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            j0, j1, i0, i1 = self._window(min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r)
            if j1 <= j0 or i1 <= i0:
                continue
            m = self._poly_mask(poly, r, j0, j1, i0, i1)
            for g in grids:
                self._mark(g, m, j0, i0, owner)

    def stamp_seg(self, x0, y0, x1, y1, r, owner, grids):
        j0, j1, i0, i1 = self._window(min(x0, x1) - r, min(y0, y1) - r, max(x0, x1) + r, max(y0, y1) + r)
        if j1 <= j0 or i1 <= i0:
            return
        X = self.X[j0:j1, i0:i1]
        Y = self.Y[j0:j1, i0:i1]
        m = self._seg_dist(X, Y, x0, y0, x1, y1) <= r
        for g in grids:
            self._mark(g, m, j0, i0, owner)

    def _static(self):
        # board edge
        for c, w in CLASSES.items():
            for g in self.grid[c]:
                e = EDGE + w / 2
                g[(self.X < e) | (self.Y < e) | (self.X > self.W - e) | (self.Y > self.H - e)] = -2
        e = EDGE + VIA_D / 2
        self.via[(self.X < e) | (self.Y < e) | (self.X > self.W - e) | (self.Y > self.H - e)] = -2
        # holes
        for h in self.holes:
            for c, w in CLASSES.items():
                for l in range(2):
                    self.stamp_seg(h["x"], h["y"], h["x"], h["y"], h["r"] + HOLE_CLR + w / 2, -2, [self.grid[c][l]])
            self.stamp_seg(h["x"], h["y"], h["x"], h["y"], h["r"] + HOLE_CLR + VIA_D / 2, -2, [self.via])
        # pads
        for p in self.pads:
            owner = self.net_id[p["net"]] if p["net"] else -3
            layers = [l for l, on in ((0, p["F"]), (1, p["Bl"])) if on]
            for c, w in CLASSES.items():
                r = CLR + w / 2
                grids = [self.grid[c][l] for l in layers]
                self.stamp_poly(p["poly"], r, owner if owner >= 0 else -2, grids)
            self.stamp_poly(p["poly"], CLR + VIA_D / 2, owner if owner >= 0 else -2, [self.via])
            if p.get("tht"):
                self._stamp_hole(p["x"], p["y"], p["drill"] / 2)
        for h in self.holes:
            self._stamp_hole(h["x"], h["y"], h["r"])
        for ko in self.keepouts:
            if ko["tracks"]:
                for c, w in CLASSES.items():
                    for l, on in ((0, ko["F"]), (1, ko["Bl"])):
                        if on:
                            self.stamp_poly(ko["poly"], w / 2 + 0.05, -2, [self.grid[c][l]])
            if ko["vias"]:
                self.stamp_poly(ko["poly"], VIA_D / 2 + 0.05, -2, [self.via])

    def _stamp_hole(self, x, y, r):
        # any via hole closer than 0.25 mm (edge-to-edge) to this hole is forbidden, whatever its net
        rr = r + 0.25 + VIA_DRILL / 2 + 0.02
        j0, j1, i0, i1 = self._window(x - rr, y - rr, x + rr, y + rr)
        if j1 > j0 and i1 > i0:
            self.hole[j0:j1, i0:i1] |= np.hypot(self.X[j0:j1, i0:i1] - x, self.Y[j0:j1, i0:i1] - y) <= rr

    # ---------------- committing copper ----------------
    def add_track(self, net, layer, x0, y0, x1, y1, w):
        k = self.net_id[net]
        self.tracks.append((net, int(layer), float(x0), float(y0), float(x1), float(y1), float(w)))
        for c, wc in CLASSES.items():
            self.stamp_seg(x0, y0, x1, y1, w / 2 + CLR + wc / 2, k, [self.grid[c][layer]])
        self.stamp_seg(x0, y0, x1, y1, w / 2 + CLR + VIA_D / 2, k, [self.via])

    def add_via(self, net, x, y):
        k = self.net_id[net]
        self.vias.append((net, float(x), float(y)))
        for c, wc in CLASSES.items():
            for l in range(2):
                self.stamp_seg(x, y, x, y, VIA_D / 2 + CLR + wc / 2, k, [self.grid[c][l]])
        self.stamp_seg(x, y, x, y, VIA_D + CLR, k, [self.via])          # via-to-via copper clearance (other nets)
        self._stamp_hole(x, y, VIA_DRILL / 2)                          # drill-to-drill spacing (any net)

    # ---------------- helpers ----------------
    def cell(self, x, y):
        return int(round(x / G)), int(round(y / G))

    def pad_cells(self, p, cls):
        k = self.net_id[p["net"]]
        out = []
        for poly in p["poly"]:
            xs = [q[0] for q in poly]
            ys = [q[1] for q in poly]
            j0, j1, i0, i1 = self._window(min(xs), min(ys), max(xs), max(ys))
            m = self._poly_mask(poly, -1.0, j0, j1, i0, i1)   # strictly inside
            for l, on in ((0, p["F"]), (1, p["Bl"])):
                if not on:
                    continue
                g = self.grid[cls][l][j0:j1, i0:i1]
                ok = m & ((g == k) | (g == -1))
                for jj, ii in zip(*np.nonzero(ok)):
                    out.append((l, i0 + ii, j0 + jj))
        return out


# ======================================================================================
def astar(bd, k, cls, sources, targets, f_only=False, margin=8.0):
    """Return list of (layer, i, j) from a source cell to a target cell, or None."""
    tset = set(targets)
    tx = np.array([t[1] for t in targets])
    ty = np.array([t[2] for t in targets])
    tcx, tcy = float(tx.mean()), float(ty.mean())
    xs = [s[1] for s in sources] + list(tx)
    ys = [s[2] for s in sources] + list(ty)
    m = int(margin / G)
    i0, i1 = max(min(xs) - m, 0), min(max(xs) + m, bd.nx - 1)
    j0, j1 = max(min(ys) - m, 0), min(max(ys) + m, bd.ny - 1)
    W = i1 - i0 + 1
    Hh = j1 - j0 + 1
    g0 = bd.grid[cls][0][j0:j1 + 1, i0:i1 + 1]
    g1 = bd.grid[cls][1][j0:j1 + 1, i0:i1 + 1]
    ok = [((g0 == k) | (g0 == -1)).ravel().tolist(), ((g1 == k) | (g1 == -1)).ravel().tolist()]
    if f_only:
        ok[1] = [False] * (W * Hh)
    vg = bd.via[j0:j1 + 1, i0:i1 + 1]
    hg = bd.hole[j0:j1 + 1, i0:i1 + 1]
    vok = (((vg == k) | (vg == -1)) & ~hg & ((g0 == k) | (g0 == -1)) & ((g1 == k) | (g1 == -1))).ravel().tolist()
    if f_only:
        vok = [False] * (W * Hh)
    INF = 1 << 60
    best = {}
    heap = []
    tlocal = {(l, i - i0, j - j0) for (l, i, j) in tset}

    def h(i, j):
        dx = abs(i + i0 - tcx)
        dy = abs(j + j0 - tcy)
        return int(10 * max(dx, dy) + 4 * min(dx, dy))

    parent = {}
    for (l, i, j) in sources:
        li, lj = i - i0, j - j0
        if not (0 <= li < W and 0 <= lj < Hh):
            continue
        idx = (l * Hh + lj) * W + li
        best[idx] = 0
        parent[idx] = -1
        heapq.heappush(heap, (h(li, lj), 0, idx))
    dirs = [(1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)]
    plane = W * Hh
    found = None
    expanded = 0
    while heap:
        f, gc, idx = heapq.heappop(heap)
        if gc > best.get(idx, INF):
            continue
        l = idx // plane
        rem = idx - l * plane
        lj, li = divmod(rem, W)
        if (l, li, lj) in tlocal:
            found = idx
            break
        expanded += 1
        if expanded > 900000:
            break
        okl = ok[l]
        for di, dj, c in dirs:
            ni, nj = li + di, lj + dj
            if ni < 0 or nj < 0 or ni >= W or nj >= Hh:
                continue
            n2 = nj * W + ni
            if not okl[n2]:
                continue
            if di and dj and not (okl[lj * W + ni] and okl[nj * W + li]):
                continue
            nidx = l * plane + n2
            ng = gc + c
            if ng < best.get(nidx, INF):
                best[nidx] = ng
                parent[nidx] = idx
                heapq.heappush(heap, (ng + h(ni, nj), ng, nidx))
        # layer change (via)
        if vok[rem]:
            nl = 1 - l
            nidx = nl * plane + rem
            ng = gc + VIA_COST
            if ok[nl][rem] and ng < best.get(nidx, INF):
                best[nidx] = ng
                parent[nidx] = idx
                heapq.heappush(heap, (ng + h(li, lj), ng, nidx))
    if found is None:
        return None
    path = []
    idx = found
    while idx != -1:
        l = idx // plane
        rem = idx - l * plane
        lj, li = divmod(rem, W)
        path.append((l, li + i0, lj + j0))
        idx = parent[idx]
    return path[::-1]


def path_to_copper(bd, net, path, w):
    """Compress a cell path into straight segments + vias and commit them."""
    segs = []
    if len(path) < 2:
        return
    start = path[0]
    prev = path[0]
    pdir = None
    for cur in path[1:]:
        if cur[0] != prev[0]:          # via
            if prev != start:
                segs.append(("t", start, prev))
            segs.append(("v", prev))
            start = cur
            pdir = None
        else:
            d = (cur[1] - prev[1], cur[2] - prev[2])
            if pdir is not None and d != pdir:
                segs.append(("t", start, prev))
                start = prev
            pdir = d
        prev = cur
    if prev != start:
        segs.append(("t", start, prev))
    for s in segs:
        if s[0] == "t":
            (l, i0, j0), (l2, i1, j1) = s[1], s[2]
            bd.add_track(net, l, i0 * G, j0 * G, i1 * G, j1 * G, w)
        else:
            l, i, j = s[1]
            bd.add_via(net, i * G, j * G)


def fanout(bd, p):
    """Connect an SMD pad of a plane net to its plane with a short track + via."""
    net = p["net"]
    k = bd.net_id[net]
    cx, cy = p["x"], p["y"]
    best = None
    for rr in np.arange(0.5, 3.01, 0.1):
        for a in np.linspace(0, 2 * math.pi, int(12 + rr * 16), endpoint=False):
            vx, vy = cx + rr * math.cos(a), cy + rr * math.sin(a)
            i, j = bd.cell(vx, vy)
            if not (0 <= i < bd.nx and 0 <= j < bd.ny):
                continue
            if bd.via[j, i] not in (-1, k) or bd.hole[j, i]:
                continue
            if bd.grid["sig"][0][j, i] not in (-1, k) or bd.grid["sig"][1][j, i] not in (-1, k):
                continue
            # straight fan-out track on F.Cu must be clear (0.3 mm wide -> use 'pwr' margin approx)
            okline = True
            n = max(2, int(rr / G) * 2)
            for t in np.linspace(0, 1, n):
                x, y = cx + (i * G - cx) * t, cy + (j * G - cy) * t
                ii, jj = bd.cell(x, y)
                if bd.grid["sig"][0][jj, ii] not in (-1, k):
                    okline = False
                    break
            if okline:
                best = (i * G, j * G)
                break
        if best:
            break
    if not best:
        return False
    bd.add_track(net, 0, cx, cy, best[0], best[1], 0.3)
    bd.add_via(net, best[0], best[1])
    return True


def route_all(geo, order_hint=None, verbose=True):
    bd = Board(geo)
    t0 = time.time()
    # 1) fan out plane nets (SMD pads only; THT pads reach the planes through their barrels)
    fails_fan = []
    smd_plane = [p for p in bd.pads if p["net"] in PLANE_NETS and not p["tht"]]
    for p in smd_plane:
        if not fanout(bd, p):
            fails_fan.append(f"{p['ref']}.{p['num']}")
    # 2) route the rest
    by_net = {}
    for p in bd.pads:
        if p["net"] and p["net"] not in PLANE_NETS:
            by_net.setdefault(p["net"], []).append(p)

    def hpwl(n):
        xs = [p["x"] for p in by_net[n]]
        ys = [p["y"] for p in by_net[n]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))
    order = sorted(by_net, key=lambda n: ({"hi": 0, "rf": 0, "pwr": 1}.get(NET_CLASS.get(n, "sig"), 2), hpwl(n)))
    if order_hint:
        order = [n for n in order_hint if n in by_net] + [n for n in order if n not in order_hint]
    failed = []
    for net in order:
        pads = by_net[net]
        if len(pads) < 2:
            continue
        cls = NET_CLASS.get(net, "sig")
        w = CLASSES[cls]
        k = bd.net_id[net]
        term = [bd.pad_cells(p, cls) for p in pads]
        if any(len(t) == 0 for t in term):
            # fall back to the pad's nearest cell
            for ti, p in enumerate(pads):
                if not term[ti]:
                    i, j = bd.cell(p["x"], p["y"])
                    term[ti] = [(0 if p["F"] else 1, i, j)]
        # connect terminals greedily (nearest first)
        tree = list(term[0])
        tree_pads = [pads[0]]
        remaining = list(range(1, len(pads)))
        ok = True
        while remaining:
            cx = np.mean([p["x"] for p in tree_pads])
            cy = np.mean([p["y"] for p in tree_pads])
            remaining.sort(key=lambda ti: math.hypot(pads[ti]["x"] - cx, pads[ti]["y"] - cy))
            ti = remaining.pop(0)
            path = None
            for margin in (6.0, 14.0, 60.0):
                path = astar(bd, k, cls, tree, term[ti], f_only=net in F_ONLY, margin=margin)
                if path:
                    break
            if not path:
                ok = False
                break
            # stubs from the exact pad centres to the first/last cells
            s_cell, e_cell = path[0], path[-1]
            path_to_copper(bd, net, path, w)
            p_end = pads[ti]
            if e_cell[0] == (0 if p_end["F"] else 1):
                bd.add_track(net, e_cell[0], e_cell[1] * G, e_cell[2] * G, p_end["x"], p_end["y"], min(w, 0.25))
            # start stub: find which pad of the tree the path started in
            for tp in tree_pads:
                if s_cell in set(bd.pad_cells(tp, cls)) or math.hypot(s_cell[1] * G - tp["x"], s_cell[2] * G - tp["y"]) < 0.8:
                    if s_cell[0] == (0 if tp["F"] else 1):
                        bd.add_track(net, s_cell[0], tp["x"], tp["y"], s_cell[1] * G, s_cell[2] * G, min(w, 0.25))
                    break
            tree += path + term[ti]
            tree_pads.append(p_end)
        if not ok:
            failed.append(net)
            if verbose:
                print("  FAILED", net)
    if verbose:
        print(f"routed in {time.time()-t0:.1f}s: {len(bd.tracks)} tracks, {len(bd.vias)} vias, "
              f"failed nets {failed}, failed fan-outs {fails_fan}")
    return bd, failed, fails_fan, order


def main():
    geo = json.load(open(sys.argv[1]))
    best = None
    order_hint = None
    for attempt in range(6):
        bd, failed, ffan, order = route_all(geo, order_hint)
        if best is None or len(failed) + len(ffan) < best[0]:
            best = (len(failed) + len(ffan), bd, failed, ffan)
        if not failed and not ffan:
            break
        order_hint = failed + [n for n in order if n not in failed]   # rip-up & retry: hardest first
    _, bd, failed, ffan = best
    json.dump(dict(tracks=bd.tracks, vias=bd.vias, failed=failed, failed_fanouts=ffan), open(sys.argv[2], "w"))
    print("wrote", sys.argv[2], "| unrouted:", failed, ffan)


if __name__ == "__main__":
    main()
