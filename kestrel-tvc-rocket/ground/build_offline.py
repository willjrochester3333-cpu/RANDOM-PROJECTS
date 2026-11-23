#!/usr/bin/env python3
"""Build ground/kestrel_mission_control.html: Mission Control as ONE self-contained file for the launch field.

The page (ground/mission_control.html) loads three.js from a CDN and the demo flight from demo_flight.csv; this
build inlines both (three.js r128, MIT licence in vendor/THREE_LICENSE), so the file works without internet and
from a USB stick. Open it in Chrome or Edge on a laptop to connect the rocket or a receiver over USB.

    python3 ground/build_offline.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'


def main():
    page = open(os.path.join(HERE, "mission_control.html"), encoding="utf-8").read()
    three = open(os.path.join(HERE, "vendor", "three-r128.min.js"), encoding="utf-8").read()
    demo = open(os.path.join(HERE, "demo_flight.csv"), encoding="utf-8").read()
    assert CDN in page, "three.js script tag not found"
    assert "</script" not in three.lower() and "</script" not in demo.lower()
    page = page.replace(CDN, '<script type="text/csv" id="demo-csv">\n' + demo + "</script>\n<script>\n" + three + "\n</script>")
    head = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
            'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>\n')
    out = os.path.join(HERE, "kestrel_mission_control.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(head + page + "\n</body></html>\n")
    print(f"wrote {out} ({os.path.getsize(out) / 1000:.0f} kB)")


if __name__ == "__main__":
    main()
