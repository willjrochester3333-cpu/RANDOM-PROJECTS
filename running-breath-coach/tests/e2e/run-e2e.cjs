// End-to-end test: real Chromium, real getUserMedia + AudioWorklet, with the
// microphone replaced by a synthetic breathing WAV file. Takes ~90 seconds
// because the fake microphone plays in real time.
//
//   npm run e2e        (needs Playwright: npm i -D playwright && npx playwright install chromium)
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
const { spawn, execFileSync } = require('node:child_process');

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  console.error('Playwright is not installed. Run: npm i -D playwright && npx playwright install chromium');
  process.exit(2);
}

const root = path.resolve(__dirname, '..', '..');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'breathpace-e2e-'));
const wav = path.join(tmp, 'breathing.wav');
const port = 8000 + Math.floor(Math.random() * 900);
const url = `http://localhost:${port}/`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`);
};

(async () => {
  execFileSync(process.execPath, [path.join(root, 'tools', 'make-test-audio.js'), wav, '150'], { stdio: 'inherit' });
  const server = spawn(process.execPath, [path.join(root, 'tools', 'serve.js'), path.join(root, 'app'), String(port)], { stdio: 'ignore' });
  let browser;
  try {
    for (let i = 0; i < 50; i++) {
      try { if ((await fetch(url)).ok) break; } catch { /* not up yet */ }
      await sleep(100);
    }
    browser = await chromium.launch({
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        `--use-file-for-fake-audio-capture=${wav}`,
        '--autoplay-policy=no-user-gesture-required',
      ],
    });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, permissions: ['microphone'] });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    await page.addInitScript(() => {
      window.__spoken = [];
      if (window.speechSynthesis) {
        const speak = window.speechSynthesis.speak.bind(window.speechSynthesis);
        window.speechSynthesis.speak = (u) => { window.__spoken.push({ text: u.text, at: performance.now() }); try { speak(u); } catch { /* no voices */ } };
      }
      localStorage.setItem('breathpace.settings.v1', JSON.stringify({
        zonePreset: 'easy', zoneLow: 26, zoneHigh: 34, warmupMin: 0, dwellSec: 5, repeatSec: 45, tones: true, voice: true,
      }));
    });
    await page.goto(url);
    await page.click('#btn-start');
    const t0 = Date.now();
    const snap = () => page.evaluate(() => {
      const e = window.breathpace.engine;
      return {
        status: e.status,
        worklet: e.source ? e.source.usingWorklet : null,
        sampleRate: e.source ? e.source.sampleRate : null,
        shown: document.querySelector('#rate-value').textContent,
        pill: document.querySelector('#run-status').textContent,
        t: e.lastUpdate ? e.lastUpdate.t : 0,
        rate: e.lastUpdate ? e.lastUpdate.coach.rate : null,
        state: e.lastUpdate ? e.lastUpdate.coach.state : null,
        cadence: e.lastUpdate && e.lastUpdate.cadence.valid ? Math.round(e.lastUpdate.cadence.spm) : null,
        spoken: window.__spoken.map((s) => s.text),
      };
    });

    // Phase 1: breathing at 30/min (inside 26–34).
    let s;
    let inZoneSeen = null;
    while (Date.now() - t0 < 38000) {
      await sleep(1000);
      s = await snap();
      if (s.rate !== null && s.state === 'in' && Math.abs(s.rate - 30) <= 3) { inZoneSeen = s; break; }
    }
    check('microphone opened through the AudioWorklet', s && s.worklet === true, s && `worklet=${s.worklet}, ${s.sampleRate} Hz`);
    check('locks on to 30 breaths/min and shows IN ZONE', Boolean(inZoneSeen),
      inZoneSeen ? `rate ${inZoneSeen.rate.toFixed(1)} at ${inZoneSeen.t.toFixed(0)} s, pill "${inZoneSeen.pill}"` : `last: ${JSON.stringify(s)}`);

    // Phase 2: breathing climbs to 46/min → expect a spoken slow-down cue.
    let slowSeen = null;
    while (Date.now() - t0 < 95000) {
      await sleep(1000);
      s = await snap();
      const said = s.spoken.find((x) => /slow down|ease right off/i.test(x));
      if (said && s.state === 'above') { slowSeen = { ...s, said }; break; }
    }
    check('says "slow down" once breathing climbs above the zone', Boolean(slowSeen),
      slowSeen ? `"${slowSeen.said}" at ${slowSeen.t.toFixed(0)} s` : `spoken: ${JSON.stringify(s.spoken)}`);
    check('reads the faster breathing correctly (46 ± 3)', Boolean(slowSeen) && Math.abs(slowSeen.rate - 46) <= 3,
      slowSeen ? `rate ${slowSeen.rate.toFixed(1)}, display "${slowSeen.shown}"` : '');
    check('status pill shows SLOW DOWN', Boolean(slowSeen) && /slow down/i.test(slowSeen.pill), slowSeen ? slowSeen.pill : '');
    check('cadence is detected (~180 steps/min)', Boolean(slowSeen) && slowSeen.cadence !== null && Math.abs(slowSeen.cadence - 180) <= 4,
      slowSeen ? `cadence ${slowSeen.cadence}` : '');
    await page.screenshot({ path: path.join(tmp, 'e2e-running.png') });

    // Stop with a long press and check the summary.
    const box = await (await page.$('#btn-stop')).boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await sleep(1300);
    await page.mouse.up();
    await sleep(500);
    const summary = await page.evaluate(() => ({
      visible: !document.querySelector('#summary-sheet').hidden,
      saved: JSON.parse(localStorage.getItem('breathpace.history.v1') || '[]').length,
      note: document.querySelector('#summary-note').textContent,
    }));
    check('hold-to-stop ends the run and shows the summary', summary.visible, summary.note);
    check('the run is saved to history', summary.saved === 1, `${summary.saved} saved`);

    // Analyse the same audio as an uploaded recording.
    await page.click('#btn-summary-close');
    await page.goto(`${url}#check`);
    await page.setInputFiles('#file-input', wav);
    await page.waitForSelector('#file-result:not([hidden])', { timeout: 60000 }).catch(() => {});
    const analysis = await page.evaluate(() => ({
      status: document.querySelector('#file-status').textContent,
      cues: Array.from(document.querySelectorAll('#file-cues li')).map((li) => li.textContent),
      avg: Array.from(document.querySelectorAll('#file-stats div')).map((d) => d.textContent).join(' | '),
    }));
    check('analyses an uploaded recording and finds the slow-down moment',
      analysis.cues.some((c) => /slow down|ease right off/i.test(c)), `${analysis.status} ${analysis.cues.slice(0, 2).join(' / ')}`);
    check('no page errors', errors.length === 0, errors.join(' | '));
    console.log(`screenshot: ${path.join(tmp, 'e2e-running.png')}`);
  } catch (err) {
    check('e2e run completed', false, err.message);
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  const failed = results.filter((r) => !r.ok).length;
  console.log(failed ? `\n${failed} check(s) failed` : '\nall end-to-end checks passed');
  process.exit(failed ? 1 : 0);
})();
