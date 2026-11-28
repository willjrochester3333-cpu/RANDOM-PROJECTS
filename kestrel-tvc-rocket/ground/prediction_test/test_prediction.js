// Landing-prediction accuracy: Mission Control's own predictLanding() (in the offline page) run on simulated flights
// (real flight code, Monte Carlo dispersions), compared with where each rocket really came down. At five moments of
// each flight: 1 s before lift-off, 1 s into the boost, just after apogee, 8 s under the open canopy, halfway down.
// The wind typed into the page is what a hand-held meter at head height would read (the simulator's 10 m wind
// scaled by the same 1/7 power law); "_nowind" repeats the pad and apogee moments with no wind typed.
//   python3 ground/prediction_test/make_flights.py a && node ground/prediction_test/test_prediction.js a
// Needs Playwright with Chromium (npm i playwright && npx playwright install chromium).
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

(async () => {
  const which = process.argv[2] || "a";
  const meta = JSON.parse(fs.readFileSync(path.join(__dirname, "flights_" + which, "meta.json"), "utf8"));
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("file://" + path.resolve(__dirname, "..", "kestrel_mission_control.html"));
  await page.waitForTimeout(2500);
  const rows = [];
  for (const m of meta) {
    const text = fs.readFileSync(m.file, "utf8");
    // the page's wind box takes the direction the wind comes FROM, as a compass bearing; the simulator's
    // wind_toward_deg is the direction it blows TOWARDS, counter-clockwise from east
    const fromDeg = ((270 - m.wind_toward_deg) % 360 + 360) % 360;
    const r = await page.evaluate(({ text, spd, from }) => {
      const ses = parseLog(text)[0];
      const f = new Flight(ses.label, "file");
      for (const row of ses.rows) f.add(row);
      app.flight = f;                                   // predictLanding reads the motor from the current flight
      const last = f.T[f.T.length - 1];
      const truth = f.posAt(last);
      const ev = f.events;
      const moments = {
        pad: f.tLaunch - 1.0,
        boost: f.tLaunch + 1.0,
        apogee: ev.apogee.t + 0.1,
        chute8: ev.chute.t + 8.0,
        mid: (ev.chute.t + (ev.landed ? ev.landed.t : last)) / 2,
      };
      const out = { motor: f.motorIndex, truth: Math.hypot(truth.e, truth.n), apo: ev.apogee.alt };
      for (const typed of [true, false]) {
        $("windSpd").value = typed ? spd.toFixed(1) : ""; $("windDir").value = typed ? from.toFixed(0) : "";
        for (const [k, t] of Object.entries(moments)) {
          const p = predictLanding(f, t, f.sample(t));
          if (!p || !isFinite(p.e)) { out[k + (typed ? "" : "_nowind")] = null; continue; }
          const miss = Math.hypot(p.e - truth.e, p.n - truth.n);
          out[k + (typed ? "" : "_nowind")] = { miss, inRing: miss <= p.unc, unc: p.unc, tLeft: p.tLeft, drift: Math.hypot(p.e - f.sample(t).e, p.n - f.sample(t).n) };
        }
      }
      return out;
    }, { text, spd: m.wind * Math.pow(2 / 10, 1 / 7), from: fromDeg });   // what a hand-held meter reads at head height
    rows.push(Object.assign({ name: path.basename(path.dirname(m.file)), wind: m.wind }, r));
  }
  await browser.close();
  const motors = { 5: "TSP-F35", 2: "TSP-E20" };
  const pct = (a, q) => { const s = a.slice().sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(q * (s.length - 1) + 0.5))]; };
  const summary = {};
  for (const mi of [5, 2]) {
    const rs = rows.filter((r) => r.motor === mi);
    const S = { n: rs.length, drift_median: pct(rs.map((r) => r.truth), 0.5), drift_max: Math.max(...rs.map((r) => r.truth)) };
    for (const k of ["pad", "boost", "apogee", "chute8", "mid", "pad_nowind", "apogee_nowind"]) {
      const v = rs.map((r) => r[k]).filter(Boolean);
      S[k] = { median_miss: +pct(v.map((x) => x.miss), 0.5).toFixed(1), p90_miss: +pct(v.map((x) => x.miss), 0.9).toFixed(1),
        max_miss: +Math.max(...v.map((x) => x.miss)).toFixed(1), in_ring: v.filter((x) => x.inRing).length + "/" + v.length };
    }
    summary[motors[mi]] = S;
  }
  console.log(JSON.stringify(summary, null, 1));
  console.log("page errors:", JSON.stringify(errors));
  fs.writeFileSync(path.join(__dirname, "flights_" + which, "results.json"), JSON.stringify({ summary, rows }, null, 1));
})();
