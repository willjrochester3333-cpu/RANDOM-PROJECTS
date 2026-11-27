import { $, h, toast, fmtTime, downloadBlob } from './dom.js';
import { drawScope, drawCurve, drawRateChart } from './charts.js';
import { renderRunStats } from './run-stats.js';
import { MicSource, decodeRecording } from '../audio/sources.js';
import { Pipeline, coachOptions } from '../engine.js';
import { analyzeSamples } from '../analysis.js';
import { cueText } from '../coach/phrases.js';
import { median } from '../dsp/periodicity.js';

const BAND_NAMES = ['150–400 Hz', '0.4–1 kHz', '1–2.5 kHz', '2.5–5 kHz', 'Tone'];
const TEST_SECONDS = 45;
const PACE_PERIOD = 3; // seconds per guided breath → 20 breaths/min

export function initCheckView({ engine, settings, isVisible }) {
  const el = {
    listen: $('#btn-listen'), rate: $('#check-rate'), conf: $('#check-conf'), level: $('#check-level'),
    scope: $('#scope'), curve: $('#curve'), bands: $('#bands'), saveClip: $('#btn-save-clip'), clipNote: $('#clip-note'),
    test: $('#btn-test'), pacer: $('#pacer'), pacerDot: $('#pacer-dot'), pacerText: $('#pacer-text'), pacerLeft: $('#pacer-left'),
    result: $('#test-result'), file: $('#file-input'), fileStatus: $('#file-status'), fileResult: $('#file-result'),
    fileChart: $('#file-chart'), fileStats: $('#file-stats'), fileCues: $('#file-cues'),
  };
  let own = null; // our own mic pipeline when no run is active
  let scope = [];
  let lastEst = null;
  let envRate = 25;
  let levelDb = null;
  let raf = 0;
  let lastDraw = 0;

  el.bands.replaceChildren(...BAND_NAMES.map((name) => h('div', { class: 'band' }, h('div', { class: 'bar' }, h('i')), h('span', {}, name))));

  const onFrame = (f) => {
    scope.push(f.activity);
    if (scope.length > 500) scope = scope.slice(-500);
    levelDb = f.levelDb;
  };
  const onEstimate = (est) => { lastEst = est; };

  // Mirror an active run so the check screen works mid-run too.
  engine.addEventListener('frame', (e) => { if (!own) onFrame(e.detail); });
  engine.addEventListener('update', (e) => {
    if (own) return;
    envRate = engine.pipeline.detector.envRate;
    onEstimate(e.detail.est);
  });
  engine.addEventListener('status', (e) => {
    if (e.detail.status === 'running' || e.detail.status === 'starting') stopListening();
    el.saveClip.disabled = !(own || (engine.running && engine.kind === 'live'));
    const busy = e.detail.status !== 'idle';
    el.listen.disabled = busy;
    el.listen.textContent = busy ? 'Showing your run' : own ? 'Stop listening' : 'Start listening';
    if (engine.running) loop();
  });

  function active() { return Boolean(own) || engine.running; }

  async function startListening() {
    if (engine.running) {
      toast('A run is in progress, so this screen shows the run’s microphone.');
      return false;
    }
    if (own) return true;
    el.listen.disabled = true;
    const source = new MicSource({ deviceId: settings.get().micDeviceId });
    try {
      await source.open();
    } catch (err) {
      el.listen.disabled = false;
      toast(err.message || String(err), 9000);
      return false;
    }
    const pipeline = new Pipeline(source, { mode: settings.get().breathMode, withCurve: true, keepAudioSec: 30 });
    envRate = pipeline.detector.envRate;
    pipeline.addEventListener('frame', (e) => onFrame(e.detail));
    pipeline.addEventListener('estimate', (e) => onEstimate(e.detail.est));
    pipeline.addEventListener('ended', () => { stopListening(); toast('The microphone was disconnected.'); });
    pipeline.start();
    own = { source, pipeline };
    scope = [];
    lastEst = null;
    el.listen.disabled = false;
    el.listen.textContent = 'Stop listening';
    el.saveClip.disabled = false;
    el.clipNote.textContent = source.label;
    window.dispatchEvent(new Event('breathpace:mic-allowed'));
    loop();
    return true;
  }

  function stopListening() {
    if (!own) return;
    own.pipeline.stop();
    own = null;
    el.listen.textContent = 'Start listening';
    el.saveClip.disabled = !(engine.running && engine.kind === 'live');
    el.clipNote.textContent = '';
  }

  el.listen.addEventListener('click', () => (own ? stopListening() : startListening()));

  function draw() {
    const cs = getComputedStyle(document.documentElement);
    drawScope(el.scope, scope, cs.getPropertyValue('--accent').trim());
    drawCurve(el.curve, lastEst && lastEst.curve, envRate, { chosenBpm: lastEst && lastEst.valid ? lastEst.rate : null });
    el.rate.textContent = lastEst && lastEst.valid ? String(Math.round(lastEst.rate)) : '–';
    el.conf.textContent = lastEst ? `${Math.round(lastEst.confidence * 100)}%` : '–';
    el.level.textContent = levelDb === null ? '–' : String(Math.round(levelDb));
    const weights = (lastEst && lastEst.weights) || [];
    el.bands.querySelectorAll('.bar i').forEach((bar, i) => {
      bar.style.height = `${Math.round(Math.min(1, weights[i] || 0) * 100)}%`;
    });
  }

  function loop() {
    if (raf) return;
    const step = (now) => {
      raf = 0;
      if (!active()) { draw(); return; }
      if (isVisible() && now - lastDraw > 60) {
        lastDraw = now;
        draw();
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  }

  el.saveClip.addEventListener('click', () => {
    const rec = own ? own.pipeline.recent : engine.recentAudio();
    if (!rec || rec.seconds < 3) {
      toast('Listen for a few seconds first.');
      return;
    }
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    downloadBlob(rec.toWav(), `breathpace-${stamp}.wav`);
  });

  // --- guided breath sound test ------------------------------------------
  let testing = false;
  el.test.addEventListener('click', async () => {
    if (testing) return;
    if (engine.running) {
      toast('Stop your run first, then run the test.');
      return;
    }
    if (!(await startListening())) return;
    testing = true;
    const det = own.pipeline.detector;
    const prevMode = det.opts.mode;
    det.setOptions({ mode: 'auto' }); // measure raw sound bursts, whatever the setting
    const startT = det.time;
    const readings = [];
    const listener = (e) => {
      const est = e.detail.est;
      if (est.t - startT >= 15 && est.valid) readings.push(est.rate);
    };
    const pipeline = own.pipeline;
    pipeline.addEventListener('estimate', listener);
    el.pacer.hidden = false;
    el.result.hidden = true;
    el.test.disabled = true;
    const t0 = performance.now();
    await new Promise((resolve) => {
      const tick = (now) => {
        const elapsed = (now - t0) / 1000;
        if (elapsed >= TEST_SECONDS || !own) { resolve(); return; }
        const phase = (elapsed % PACE_PERIOD) / (PACE_PERIOD / 2);
        const inhale = phase < 1;
        const u = inhale ? phase : phase - 1;
        const ease = 0.5 - 0.5 * Math.cos(Math.PI * u);
        const scale = inhale ? 0.45 + 0.55 * ease : 1 - 0.55 * ease;
        el.pacerDot.style.transform = `scale(${scale.toFixed(3)})`;
        el.pacerText.textContent = inhale ? 'In' : 'Out';
        el.pacerLeft.textContent = `${Math.ceil(TEST_SECONDS - elapsed)} s left`;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    pipeline.removeEventListener('estimate', listener);
    det.setOptions({ mode: prevMode });
    el.pacer.hidden = true;
    el.test.disabled = false;
    testing = false;
    el.result.hidden = false;
    if (readings.length < 8) {
      el.result.textContent = `Couldn't hear a steady rhythm (${readings.length} clear readings). Move the mic a little closer to your mouth, breathe louder, and try again.`;
      return;
    }
    const m = median(readings);
    const target = 60 / PACE_PERIOD;
    if (Math.abs(m - target) <= 3.5) {
      settings.set({ breathMode: 'auto' });
      el.result.textContent = `Heard one sound pattern per breath (${Math.round(m)}/min while pacing ${target}). Counting is set to automatic. You're ready to run.`;
    } else if (Math.abs(m - 2 * target) <= 6) {
      settings.set({ breathMode: 'double' });
      el.result.textContent = `Your inhales and exhales sound alike (${Math.round(m)} sounds/min while pacing ${target} breaths). BreathPace will now count each in-and-out pair as one breath.`;
    } else {
      el.result.textContent = `Measured ${Math.round(m)}/min while pacing ${target}/min, which doesn't match one or two sounds per breath. Check the mic position and try again in a quieter spot.`;
    }
  });

  // --- analyse a recording ------------------------------------------------
  el.file.addEventListener('change', async () => {
    const file = el.file.files && el.file.files[0];
    el.file.value = '';
    if (!file) return;
    if (file.size > 400 * 1024 * 1024) {
      el.fileStatus.textContent = 'That file is over 400 MB. Trim it to under an hour or so and try again.';
      return;
    }
    el.fileResult.hidden = true;
    el.fileStatus.textContent = `Decoding ${file.name}…`;
    try {
      const { samples, sampleRate, duration } = await decodeRecording(file);
      const s = settings.get();
      const res = await analyzeSamples(samples, sampleRate, coachOptions(s), {
        mode: s.breathMode,
        onProgress: (p) => { el.fileStatus.textContent = `Analysing ${fmtTime(duration)} of audio… ${Math.round(p * 100)}%`; },
      });
      el.fileStatus.textContent = `${file.name}: breathing detected for ${Math.round(res.coveredShare * 100)}% of the recording.`;
      el.fileResult.hidden = false;
      const zone = { low: s.zoneLow, high: s.zoneHigh };
      drawRateChart(el.fileChart, { series: res.series, zone, cues: res.cues });
      renderRunStats(el.fileStats, { ...res, cues: res.cues });
      const spoken = res.cues.filter(([, type]) => type !== 'locked');
      el.fileCues.replaceChildren(...(spoken.length
        ? spoken.slice(0, 40).map(([t, , , cue]) => h('li', {}, h('b', {}, fmtTime(t)), ' ', cueText(cue, 'detailed')))
        : [h('li', {}, 'The coach would have stayed quiet: no cues.')]));
    } catch (err) {
      el.fileStatus.textContent = err.message || String(err);
    }
  });

  return {
    onShow() { if (active()) loop(); else draw(); },
    onHide() { /* keep listening; drawing pauses while hidden */ },
  };
}
