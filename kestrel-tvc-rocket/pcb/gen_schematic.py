#!/usr/bin/env python3
"""Generate the KiCad 7 schematic (kestrel_fc.kicad_sch) from circuit.py.

Every pin gets a net label placed exactly on its connection point (a clean, netlist-style schematic),
NC pins get no-connect flags and every power net gets a PWR_FLAG so KiCad's ERC is satisfied.
Verified by exporting the netlist with kicad-cli and comparing it against circuit.py (check_netlist.py).
"""
import copy
import os
import uuid

import circuit as C
from sexp import Q, dump, find, find1, parse

HERE = os.path.dirname(os.path.abspath(__file__))
SYMDIR = "/usr/share/kicad/symbols"
PROJECT = "kestrel_fc"
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kestrel-fc-root"))


def uid(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "kestrel-fc-" + seed))


_libcache = {}


def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    path = os.path.join(HERE, "kestrel.kicad_sym") if lib == "kestrel" else os.path.join(SYMDIR, lib + ".kicad_sym")
    if path not in _libcache:
        _libcache[path] = parse(open(path).read())
    tree = _libcache[path]
    syms = {s[1]: s for s in find(tree, "symbol")}
    s = copy.deepcopy(syms[name])
    ext = find1(s, "extends")
    if ext:
        parent = copy.deepcopy(syms[ext[1]])
        if find1(parent, "extends"):
            raise RuntimeError("nested extends not supported")
        # child properties override; graphics/pins from parent
        child_props = {p[1]: p for p in find(s, "property")}
        out = [s[0], Q(name)]
        for e in parent[2:]:
            if isinstance(e, list) and e[0] == "property" and e[1] in child_props:
                out.append(child_props.pop(e[1]))
            elif isinstance(e, list) and e[0] == "symbol":
                sub = copy.deepcopy(e)
                sub[1] = Q(sub[1].replace(parent[1], name, 1))
                out.append(sub)
            else:
                out.append(e)
        for p in child_props.values():
            out.insert(4, p)
        s = out
    s[1] = Q(lib_id)
    return s


def pins_of(sym):
    """[(number, name, type, x, y, angle)] in library coordinates (Y up)."""
    out = []
    for sub in find(sym, "symbol"):
        for p in find(sub, "pin"):
            at = find1(p, "at")
            num = find1(p, "number")[1]
            nm = find1(p, "name")[1]
            out.append((str(num), str(nm), p[1], float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return out


def prop(name, value, x, y, hide=False, size=1.27):
    eff = ["effects", ["font", ["size", size, size]]]
    if hide:
        eff.append("hide")
    return ["property", Q(name), Q(value), ["at", x, y, 0], eff]


def label(net, x, y, ang, seed):
    just = {0: ["justify", "left", "bottom"], 90: ["justify", "left", "bottom"], 180: ["justify", "right", "bottom"],
            270: ["justify", "right", "bottom"]}[ang]
    return ["label", Q(net), ["at", x, y, ang], ["fields_autoplaced"], ["effects", ["font", ["size", 1.0, 1.0]], just],
            ["uuid", uid(seed)]]


FLAG_NETS = ["GND", "+3V3", "+3V3_GPS", "VBAT_IN", "VBAT_RP", "VBAT_SW", "5V_SERVO", "5V_LOG", "VSYS", "AUX_5V", "VIO_GPS"]

BLOCK_ORIGIN = {  # schematic placement grid (mm) on an A2 sheet per functional block
    "power": (30, 40), "servo_buck": (30, 160), "logic_buck": (30, 250), "mcu": (215, 60),
    "sensors": (330, 60), "gps": (330, 200), "servos": (440, 60), "ui": (440, 200), "misc": (500, 300),
}


def main():
    lib_syms = {}
    body = []
    placed = {}
    counters = {}
    for p in C.PARTS:
        lib_syms.setdefault(p["lib"], lib_symbol(p["lib"]))
        blk = p["block"]
        k = counters.get(blk, 0)
        counters[blk] = k + 1
        ox, oy = BLOCK_ORIGIN[blk]
        if p["lib"].startswith("Connector_Generic:Conn_01x20"):
            X, Y = ox + (0 if p["ref"] == "J10" else 60), oy
        else:
            X, Y = ox + (k % 4) * 25.4, oy + (k // 4) * 25.4
        X, Y = round(X / 2.54) * 2.54, round(Y / 2.54) * 2.54
        placed[p["ref"]] = (X, Y)
        sym = lib_syms[p["lib"]]
        inst = ["symbol", ["lib_id", Q(p["lib"])], ["at", X, Y, 0], ["unit", 1], ["in_bom", "no" if p["dnp"] else "yes"],
                ["on_board", "yes"], ["dnp", "yes" if p["dnp"] else "no"], ["uuid", uid("sym-" + p["ref"])]]
        inst.append(prop("Reference", p["ref"], X + 3.0, Y - 4.0))
        inst.append(prop("Value", p["value"], X + 3.0, Y + 4.0))
        inst.append(prop("Footprint", p["fp"], X, Y, hide=True))
        inst.append(prop("Datasheet", "", X, Y, hide=True))
        if p["lcsc"]:
            inst.append(prop("LCSC", p["lcsc"], X, Y, hide=True))
        inst.append(prop("MPN", p["mpn"], X, Y, hide=True))
        for (num, nm, typ, px, py, pa) in pins_of(sym):
            inst.append(["pin", Q(num), ["uuid", uid(f"pin-{p['ref']}-{num}-{nm}")]])
        inst.append(["instances", ["project", Q(PROJECT), ["path", Q("/" + ROOT_UUID), ["reference", Q(p["ref"])], ["unit", 1]]]])
        body.append(inst)
        # labels / no-connects at every pin
        seen = set()
        for (num, nm, typ, px, py, pa) in pins_of(sym):
            if (num, px, py) in seen:
                continue
            seen.add((num, px, py))
            sx, sy = round(X + px, 4), round(Y - py, 4)
            net = p["pins"].get(num, "__missing__")
            if net == "__missing__":
                raise RuntimeError(f"{p['ref']} pin {num} ({nm}) has no net assignment")
            if net is None:
                body.append(["no_connect", ["at", sx, sy], ["uuid", uid(f"nc-{p['ref']}-{num}")]])
            else:
                ang = int((pa + 180) % 360)
                body.append(label(net, sx, sy, ang, f"lbl-{p['ref']}-{num}-{px}-{py}"))
    # PWR_FLAGs on every net that feeds power_in pins (or carries supply)
    flag = lib_symbol("power:PWR_FLAG")
    lib_syms["power:PWR_FLAG"] = flag
    for i, net in enumerate(FLAG_NETS):
        X, Y = 500 + (i % 6) * 15.24, 380 + (i // 6) * 15.24
        ref = f"#FLG{i+1:02d}"
        inst = ["symbol", ["lib_id", Q("power:PWR_FLAG")], ["at", X, Y, 0], ["unit", 1], ["in_bom", "yes"], ["on_board", "yes"],
                ["dnp", "no"], ["uuid", uid("flag" + net)], prop("Reference", ref, X, Y - 3, hide=True),
                prop("Value", "PWR_FLAG", X, Y + 3), prop("Footprint", "", X, Y, hide=True), prop("Datasheet", "", X, Y, hide=True),
                ["pin", Q("1"), ["uuid", uid("flagpin" + net)]],
                ["instances", ["project", Q(PROJECT), ["path", Q("/" + ROOT_UUID), ["reference", Q(ref)], ["unit", 1]]]]]
        body.append(inst)
        body.append(label(net, X, Y, 270, "flaglbl" + net))
    # title notes
    texts = [
        "KESTREL FC v3.0 - TVC + fin-tab flight computer (Raspberry Pi Pico 2 W carrier, 7 servo ports, telemetry-radio socket)",
        "Fully JLCPCB-assembled (SMD + THT headers): no soldering required.",
        "Bucks: Vout = 0.768 V x (1 + 55k/10k) = 4.99 V. GPS footprint: u-blox MAX (ATGM336H-5N31 or MAX-M10S). R24 not fitted (passive antenna).",
        "Net labels on every pin define the connectivity; see circuit.py for the source of truth.",
    ]
    for i, t in enumerate(texts):
        body.append(["text", Q(t), ["at", 30, 15 + i * 5, 0], ["effects", ["font", ["size", 2.0 if i == 0 else 1.5, 2.0 if i == 0 else 1.5]],
                                                                  ["justify", "left", "bottom"]], ["uuid", uid("txt%d" % i)]])
    sch = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"], ["uuid", ROOT_UUID], ["paper", Q("A2")],
           ["title_block", ["title", Q("KESTREL FC - TVC flight computer")], ["date", Q("2026-11-27")], ["rev", Q("3.0")],
            ["company", Q("KESTREL-2 rocket project")], ["comment", 1, Q("Generated by pcb/gen_schematic.py")]],
           ["lib_symbols"] + list(lib_syms.values())] + body + [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]]
    out = os.path.join(HERE, PROJECT + ".kicad_sch")
    with open(out, "w") as fh:
        fh.write(dump(sch) + "\n")
    print("wrote", out, len(C.PARTS), "parts")


if __name__ == "__main__":
    main()
