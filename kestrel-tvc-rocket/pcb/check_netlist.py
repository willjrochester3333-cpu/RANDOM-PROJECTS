#!/usr/bin/env python3
"""Check the KiCad-exported netlist (kicad-cli sch export netlist) against circuit.py, pin by pin,
plus electrical-rule checks KiCad 7's CLI can't run (no `sch erc` until KiCad 8):
  * every circuit pin is on the intended net, and no extra connections exist
  * every net has >= 2 pins; power nets have a source; no output-output conflicts
Usage: python3 check_netlist.py <netlist.net>
"""
import sys
from collections import defaultdict

import circuit as C
from sexp import find, find1, parse


def main(path):
    tree = parse(open(path).read())
    nets = find1(tree, "nets")
    got = {}
    pin_types = {}
    net_pins = defaultdict(list)
    for n in find(nets, "net"):
        name = str(find1(n, "name")[1]).lstrip("/")
        for node in find(n, "node"):
            ref = str(find1(node, "ref")[1])
            pin = str(find1(node, "pin")[1])
            if ref.startswith("#FLG"):
                net_pins[name].append((ref, pin, "power_out"))
                continue
            got[(ref, pin)] = name
            pt = find1(node, "pintype")
            pin_types[(ref, pin)] = str(pt[1]) if pt else "?"
            net_pins[name].append((ref, pin, pin_types[(ref, pin)]))
    errors = []
    want = {}
    for p in C.PARTS:
        for pin, net in p["pins"].items():
            if net is None or pin == "MP":
                continue
            want[(p["ref"], pin)] = net
    for k, net in want.items():
        g = got.get(k)
        if g is None:
            errors.append(f"{k} expected on {net}, not in netlist")
        elif g != net:
            errors.append(f"{k} expected {net}, got {g}")
    for k, g in got.items():
        if k not in want and not g.startswith("unconnected-"):
            errors.append(f"{k} unexpectedly connected to {g}")
    # ERC-style checks
    for name, pins in net_pins.items():
        real = [p for p in pins if not p[0].startswith("#FLG")]
        if name.startswith("unconnected-"):
            continue
        if len(real) < 2:
            errors.append(f"net {name} has fewer than 2 pins: {real}")
        types = [t for _, _, t in pins]
        from gen_schematic import FLAG_NETS
        if "power_in" in types and not any(t in ("power_out",) for t in types) and name not in FLAG_NETS:
            errors.append(f"net {name}: power_in pins but no power source / PWR_FLAG")
        outs = [p for p in real if p[2] == "output"]
        if len(outs) > 1:
            errors.append(f"net {name}: multiple outputs {outs}")
    print(f"netlist: {len(got)} connected pins on {len([n for n in net_pins if not n.startswith('unconnected-')])} nets")
    if errors:
        print("ERRORS:")
        for e in errors:
            print("  ", e)
        sys.exit(1)
    print("netlist matches circuit.py exactly; ERC checks passed")


if __name__ == "__main__":
    main(sys.argv[1])
