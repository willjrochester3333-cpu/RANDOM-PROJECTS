import { $, fmtTime, fmtPct, holdButton, toast } from './dom.js';
import { drawRateChart } from './charts.js';
import { renderRunStats } from './run-stats.js';
import { cueText } from '../coach/phrases.js';
import { zoneName } from '../store/settings.js';
import { STATE_CODES } from '../engine.js';

const GAUGE_MIN = 10;
const GAUGE_MAX = 70;
const pct = (bpm) => ((Math.min(GAUGE_MAX, Math.max(GAUGE_MIN, bpm)) - GAUGE_MIN) / (GAUGE_MAX - GAUGE_MIN)) * 100;

const STATUS_TEXT = {
  idle: 'Ready',
  starting: 'Starting',
  listening: 'Listening',
  in: 'In zone',
  above: 'Slow down',
  below: 'Speed up',
  warmup: 'Warming up',
  lost: 'No signal',
  paused: 'Paused',
};

const SHOW_CAPTION = new Set(['slow', 'speed', 'inzone', 'locked', 'back', 'lost', 'status']);

export function initRunView({ engine, settings }) {
  const view = $('#view-run');
  const el = {
    status: $('#run-status'), source: $('#run-source'), rate: $('#rate-value'), ring: $('#breath-ring i'),
    zone: $('#gauge-zone'), marker: $('#gauge-marker'), gauge: $('#zone-gauge'), caption: $('#cue-caption'),
    time: $('#stat-time'), inzone: $('#stat-inzone'), cadence: $('#stat-cadence'), spb: $('#stat-spb'), unit: $('#rate-unit'),
    chart: $('#run-chart'), meter: $('#meter-fill'), quality: $('#signal-quality'),
    idle: $('#controls-idle'), running: $('#controls-running'), extra: $('#controls-extra'), hint: $('#run-hint'),
    start: $('#btn-start'), demo: $('#btn-demo'), pause: $('#btn-pause'), stop: $('#btn-stop'),
    learn: $('#btn-learn'), lock: $('#btn-lock'),
    overlay: $('#lock-overlay'), lockState: $('#lock-state'), lockRate: $('#lock-rate'), lockZone: $('#lock-zone'),
    sheet: $('#summary-sheet'),
  };
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let activityTarget = 0;
  let activityShown = 0;
  let raf = 0;
  let lastUpdate = null;
  let captionTimer = null;
  let hotUntil = 0;

  function renderZone() {
    const s = settings.get();
    el.zone.style.left = `${pct(s.zoneLow)}%`;
    el.zone.style.width = `${pct(s.zoneHigh) - pct(s.zoneLow)}%`;
    $('#zone-chip-name').textContent = zoneName(s);
    $('#zone-chip-range').textContent = `${s.zoneLow}–${s.zoneHigh}`;
    el.gauge.setAttribute('aria-label', `Target zone ${s.zoneLow} to ${s.zoneHigh} breaths per minute`);
    document.getElementById('app').classList.toggle('hide-cadence', !s.showCadence);
    if (lastUpdate) render(lastUpdate);
    else drawChart(0);
    if (engine.status === 'idle') showIdleReadout();
  }

  function showIdleReadout() {
    const s = settings.get();
    el.rate.textContent = `${s.zoneLow}–${s.zoneHigh}`;
    el.unit.textContent = 'target breaths / min';
  }

  function setStatus(stateAttr, textKey) {
    view.dataset.state = stateAttr;
    el.status.textContent = STATUS_TEXT[textKey] || textKey;
  }

  function drawChart(now) {
    const s = settings.get();
    const series = engine.session && engine.running ? engine.session.series.slice() : [];
    if (lastUpdate && lastUpdate.coach.rate !== null) {
      series.push([lastUpdate.t, lastUpdate.coach.rate, STATE_CODES[lastUpdate.coach.state]]);
    }
    drawRateChart(el.chart, {
      series,
      zone: { low: s.zoneLow, high: s.zoneHigh },
      cues: engine.running ? engine.session.cues : [],
      windowSec: 15 * 60,
      now,
    });
  }

  function render(u) {
    const s = settings.get();
    const { t, est, coach, cadence, summary } = u;
    const paused = engine.status === 'paused';
    const warm = coach.state === 'below' && t < s.warmupMin * 60;
    setStatus(paused ? 'paused' : coach.state, paused ? 'paused' : warm ? 'warmup' : coach.state);
    el.rate.textContent = coach.rate === null ? '–' : String(Math.round(coach.rate));
    el.unit.textContent = 'breaths / min';
    if (coach.rate !== null) {
      el.marker.hidden = false;
      el.marker.style.left = `${pct(coach.rate)}%`;
    } else {
      el.marker.hidden = true;
    }
    el.time.textContent = fmtTime(t);
    el.inzone.textContent = fmtPct(summary.inZoneShare);
    if (cadence && cadence.valid) {
      el.cadence.textContent = String(Math.round(cadence.spm));
      el.spb.textContent = coach.rate ? `${(cadence.spm / coach.rate).toFixed(1)} steps/breath` : '';
    } else {
      el.cadence.textContent = '–';
      el.spb.textContent = '';
    }
    const q = !est.valid ? (est.confidence > 0.3 ? 1 : 0) : est.confidence > 0.85 ? 4 : est.confidence > 0.65 ? 3 : 2;
    el.quality.dataset.q = String(q);
    el.quality.title = `Rhythm clarity ${Math.round(est.confidence * 100)}%`;
    drawChart(t);
    if (!el.overlay.hidden) renderLock(u);
  }

  function renderLock(u) {
    const s = settings.get();
    const state = u ? u.coach.state : 'listening';
    el.lockState.dataset.state = state;
    el.lockState.textContent = STATUS_TEXT[state] || '';
    el.lockRate.textContent = u && u.coach.rate !== null ? String(Math.round(u.coach.rate)) : '–';
    el.lockZone.textContent = `Target ${s.zoneLow}–${s.zoneHigh} · ${fmtTime(u ? u.t : 0)}`;
  }

  function animate() {
    activityShown += (activityTarget - activityShown) * 0.3;
    el.ring.style.setProperty('--a', reduceMotion ? '0.5' : activityShown.toFixed(3));
    raf = engine.running ? requestAnimationFrame(animate) : 0;
  }

  engine.addEventListener('status', (e) => {
    const { status } = e.detail;
    const active = status === 'running' || status === 'paused';
    el.idle.hidden = active;
    el.running.hidden = !active;
    el.extra.hidden = !active;
    el.hint.hidden = active;
    el.pause.textContent = status === 'paused' ? 'Resume' : 'Pause';
    el.start.disabled = status === 'starting';
    el.demo.disabled = status === 'starting';
    if (status === 'starting') {
      setStatus('listening', 'starting');
      el.rate.textContent = '–';
      el.unit.textContent = 'breaths / min';
    } else if (status === 'running') {
      if (lastUpdate) render(lastUpdate);
      else setStatus('listening', 'listening');
      el.source.textContent = engine.source ? engine.source.label : '';
      if (!raf) raf = requestAnimationFrame(animate);
    } else if (status === 'paused') {
      setStatus('paused', 'paused');
    } else {
      lastUpdate = null;
      activityTarget = 0;
      setStatus('idle', 'idle');
      showIdleReadout();
      el.marker.hidden = true;
      el.source.textContent = '';
      el.time.textContent = '0:00';
      el.inzone.textContent = '–';
      el.cadence.textContent = '–';
      el.spb.textContent = '';
      el.quality.dataset.q = '0';
      el.meter.style.width = '0';
      el.ring.style.setProperty('--a', '0');
      el.overlay.hidden = true;
      drawChart(0);
    }
  });

  engine.addEventListener('update', (e) => {
    lastUpdate = e.detail;
    render(e.detail);
  });

  engine.addEventListener('frame', (e) => {
    const f = e.detail;
    activityTarget = f.activity;
    const level = Math.max(0, Math.min(1, (f.levelDb + 70) / 70));
    el.meter.style.width = `${(level * 100).toFixed(1)}%`;
    const now = performance.now();
    if (f.peak >= 0.98) hotUntil = now + 1500;
    el.meter.classList.toggle('hot', now < hotUntil);
  });

  engine.addEventListener('cue', (e) => {
    const cue = e.detail;
    if (!SHOW_CAPTION.has(cue.type)) return;
    el.caption.textContent = cueText(cue, 'detailed');
    clearTimeout(captionTimer);
    captionTimer = setTimeout(() => { el.caption.textContent = ''; }, 10000);
  });

  engine.addEventListener('error', (e) => toast(e.detail.message, 8000));
  engine.addEventListener('stopped', (e) => showSummary(e.detail));

  async function begin(kind) {
    try {
      await engine.start(kind);
    } catch (err) {
      toast(err.message || String(err), 9000);
    }
  }
  el.start.addEventListener('click', () => begin('live'));
  el.demo.addEventListener('click', () => begin('demo'));
  el.pause.addEventListener('click', () => {
    if (engine.status === 'running') engine.pause();
    else if (engine.status === 'paused') engine.resume();
  });
  holdButton(el.stop, 900, () => engine.stop());

  el.learn.addEventListener('click', () => {
    const z = engine.learnZone();
    if (!z) {
      toast('Run at your target effort for about a minute first, then tap again.');
      return;
    }
    settings.set({ zoneLow: z.low, zoneHigh: z.high, zonePreset: 'custom' });
    engine.feedback.say(`Zone set to ${z.low} to ${z.high}.`);
    toast(`Zone set to ${z.low}–${z.high} breaths/min (you were at ${Math.round(z.median)}).`);
  });

  el.lock.addEventListener('click', () => {
    el.overlay.hidden = false;
    renderLock(lastUpdate);
  });
  holdButton($('#btn-unlock'), 1200, () => { el.overlay.hidden = true; });

  function showSummary({ run, saved }) {
    renderRunStats($('#summary-stats'), run);
    $('#summary-note').textContent = saved
      ? 'Saved to Runs on this phone.'
      : run.kind === 'demo'
        ? 'Demo runs are not saved.'
        : 'Runs shorter than 30 seconds are not saved.';
    el.sheet.hidden = false;
    requestAnimationFrame(() => drawRateChart($('#summary-chart'), { series: run.series, zone: run.zone, cues: run.cues }));
    $('#btn-summary-close').focus();
  }
  $('#btn-summary-close').addEventListener('click', () => { el.sheet.hidden = true; });

  settings.addEventListener('change', renderZone);
  window.addEventListener('resize', () => drawChart(lastUpdate ? lastUpdate.t : 0));
  renderZone();
  return { redraw: () => drawChart(lastUpdate ? lastUpdate.t : 0) };
}
