// Checks Mission Control's radio decoder (the TLM block inside mission_control.html) against frames made by an
// independent implementation (ground/radio_frames.py) and against pymavlink reference frames.
//   python3 ground/radio_frames.py demo /tmp/demo_radio.bin && node ground/test_radio.mjs /tmp/demo_radio.bin
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const page = fs.readFileSync(path.join(here, "mission_control.html"), "utf8");
const block = page.slice(page.indexOf("/* TLM-BEGIN */"), page.indexOf("/* TLM-END */"));
const TLM = new Function(block + "\nreturn TLM;")();
let pass = 0, fail = 0;
const check = (c, msg) => { if (c) pass++; else { fail++; console.log("FAIL", msg); } };
const hex = (u8) => Buffer.from(u8).toString("hex");

// 1. pymavlink reference frames (MAVLink 1.0, sys 255 comp 190, seq 0)
check(hex(TLM.heartbeat(0)) === "fe0900ffbe000000000006080004034921", "HEARTBEAT matches pymavlink");
const rsRef = Buffer.from("fe0900ffbe6d03000100b4aa5a282dce56", "hex");
let d = new TLM.Decoder(), got = null;
for (const b of rsRef) got = d.feed(b) || got;
check(got && got.msgid === 109 && TLM.radioStatus(got.payload).rssi === 180 && TLM.radioStatus(got.payload).txbuf === 90, "RADIO_STATUS decoded");
check(Math.abs(TLM.dbm(180) - (180 / 1.9 - 127)) < 1e-9, "RSSI to dBm");

// 2. the simulated flight as radio bytes from the Python encoder, decoded here; compared with Python's own decode
const cap = process.argv[2];
const bytes = fs.readFileSync(cap);
const ref = JSON.parse(execFileSync("python3", ["-c", `
import sys, json; sys.path.insert(0, ${JSON.stringify(here)})
import radio_frames as R
fr = R.Decoder().feed(open(${JSON.stringify(cap)}, "rb").read())
fast = [R.fast(f["payload"]) for f in fr if f["msgid"] == R.FAST]
slow = [R.slow(f["payload"]) for f in fr if f["msgid"] == R.SLOW]
print(json.dumps(dict(n=len(fr), nfast=len(fast), nslow=len(slow), t_first=fast[0]["t"], t_last=fast[-1]["t"],
  alt_max=max(f["alt"] for f in fast), lat=slow[-1]["lat_e7"], roll_last=fast[-1]["roll"], state_hist=sorted(set(f["state"] for f in fast)))))
`]).toString());
d = new TLM.Decoder(); const frames = [];
for (const b of bytes) { const f = d.feed(b); if (f) frames.push(f); }
const fast = frames.filter((f) => f.msgid === TLM.FAST).map((f) => TLM.fast(f.payload));
const slow = frames.filter((f) => f.msgid === TLM.SLOW).map((f) => TLM.slow(f.payload));
check(frames.length === ref.n && fast.length === ref.nfast && slow.length === ref.nslow, `frame counts ${frames.length}/${fast.length}/${slow.length} vs ${ref.n}/${ref.nfast}/${ref.nslow}`);
check(fast[0].t === ref.t_first && fast[fast.length - 1].t === ref.t_last, "first / last motion frame times");
check(Math.abs(Math.max(...fast.map((f) => f.alt)) - ref.alt_max) < 1e-3, "highest altitude carried");
check(Math.round(slow[slow.length - 1].lat * 1e7) === ref.lat, "GPS latitude at full precision");
check(fast[fast.length - 1].roll === ref.roll_last, "roll angle");
check(JSON.stringify([...new Set(fast.map((f) => f.state))].sort()) === JSON.stringify(ref.state_hist), "flight states seen");
check(d.bad === 0, "no rejected bytes in a clean stream");
const inflight = fast.filter((f) => f.state >= 3 && f.state <= 5);
const span = (inflight[inflight.length - 1].t - inflight[0].t) / 1000;
check(Math.abs(inflight.length / span - 50) < 1.5, `50 motion frames per second in flight (${(inflight.length / span).toFixed(1)})`);

// 3. a damaged link: 2 % of 60-byte chunks lost, 1 byte in 2000 flipped, random read sizes. Every frame the damage did
//    not touch must still come through (a bad neighbour must not cost a good frame), and no damaged frame may pass.
const bounds = []; { let i = 0; while (i < bytes.length) { const n = bytes[i + 1] + 8; bounds.push([i, i + n]); i += n; } }
let rnd = 12345; const rand = () => (rnd = (rnd * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const damaged = [], hurt = new Uint8Array(bytes.length);
for (let i = 0; i < bytes.length; i += 60) {
  if (rand() < 0.02) { hurt.fill(1, i, Math.min(bytes.length, i + 60)); continue; }
  for (let j = i; j < Math.min(bytes.length, i + 60); j++) { const flip = rand() < 0.0005; if (flip) hurt[j] = 1; damaged.push(flip ? bytes[j] ^ 0x5a : bytes[j]); }
}
const intact = bounds.filter(([a, b]) => !hurt.subarray(a, b).some((x) => x)).length;
d = new TLM.Decoder(); let n2 = 0;
for (let i = 0; i < damaged.length;) { const k = 1 + Math.floor(rand() * 200); for (const b of damaged.slice(i, i + k)) if (d.feed(b)) n2++; i += k; }
check(bounds.length === frames.length, "frame boundaries");
check(n2 === intact, `damaged link: ${n2} frames decoded, ${intact} were untouched by the damage (of ${frames.length})`);
console.log(`${pass} checks passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
