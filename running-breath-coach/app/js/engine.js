// Wires an audio source through the detector, the coach and the feedback,
// and records the run. Browser-only (uses DOM events and the Wake Lock API).

import { BreathDetector } from './dsp/breath-detector.js';
import { CadenceDetector } from './dsp/cadence.js';
import { Coach } from './coach/coach.js';
import { MicSource, DemoSource } from './audio/sources.js';
import { RecentAudio } from './audio/wav.js';
import { history } from './store/settings.js';

export function coachOptions(s) {
  return {
    zoneLow: s.zoneLow,
    zoneHigh: s.zoneHigh,
    warmupSec: s.warmupMin * 60,
    dwellSec: s.dwellSec,
    repeatSec: s.repeatSec,
    inZoneCue: s.inZoneCue,
    statusEveryMin: s.statusEveryMin,
  };
}

export const STATE_CODES = { listening: 0, in: 1, above: 2, below: 3, lost: 4 };

const emit = (target, type, detail) => target.dispatchEvent(new CustomEvent(type, { detail }));

/** Source → breath detector + cadence detector. */
export class Pipeline extends EventTarget {
  constructor(source, { mode = 'auto', withCurve = false, keepAudioSec = 0 } = {}) {
    super();
    this.source = source;
    this.paused = false;
    this.detector = new BreathDetector(source.sampleRate, { mode, withCurve });
    this.cadence = new CadenceDetector(this.detector.frontend.subRate);
    this.recent = keepAudioSec ? new RecentAudio(source.sampleRate, keepAudioSec) : null;
    this.detector.onFrontendFrame = (f) => this.cadence.pushImpacts(f.impact);
    this.detector.onFrame = (f) => emit(this, 'frame', f);
    this.detector.onEstimate = (est) => emit(this, 'estimate', { est, cadence: this.cadence.estimate() });
    source.onAudio = (chunk) => {
      if (this.paused) return;
      if (this.recent) this.recent.push(chunk);
      this.detector.pushAudio(chunk);
    };
    source.onEnded = () => emit(this, 'ended');
  }

  start() { this.source.start(); }
  stop() { this.source.stop(); }
}

class ScreenWakeLock {
  constructor() {
    this.wanted = false;
    this.lock = null;
    document.addEventListener('visibilitychange', () => {
      if (this.wanted && document.visibilityState === 'visible') this._request();
    });
  }

  async _request() {
    if (!('wakeLock' in navigator) || this.lock) return;
    try {
      this.lock = await navigator.wakeLock.request('screen');
      this.lock.addEventListener('release', () => { this.lock = null; });
    } catch { /* denied or unsupported: the screen may sleep */ }
  }

  acquire() { this.wanted = true; return this._request(); }

  release() {
    this.wanted = false;
    if (this.lock) this.lock.release().catch(() => {});
    this.lock = null;
  }
}

export class RunEngine extends EventTarget {
  constructor({ settings, feedback }) {
    super();
    this.settings = settings;
    this.feedback = feedback;
    this.status = 'idle'; // idle | starting | running | paused
    this.wakeLock = new ScreenWakeLock();
    settings.addEventListener('change', () => this.applySettings());
  }

  get running() { return this.status === 'running' || this.status === 'paused'; }

  _setStatus(status) {
    this.status = status;
    emit(this, 'status', { status, kind: this.kind });
  }

  /** Start a run. Call from a tap handler (`kind` = 'live' | 'demo'). */
  async start(kind = 'live') {
    if (this.status !== 'idle') return;
    const s = this.settings.get();
    this.feedback.unlock();
    this._setStatus('starting');
    const source = kind === 'demo'
      ? new DemoSource({ zoneLow: s.zoneLow, zoneHigh: s.zoneHigh, speed: s.demoSpeed })
      : new MicSource({ deviceId: s.micDeviceId });
    try {
      await source.open();
    } catch (err) {
      this._setStatus('idle');
      throw err;
    }
    this.kind = kind;
    this.source = source;
    this.coach = new Coach(coachOptions(s));
    this.timeOffset = 0;
    this.lastT = 0;
    this.lastSeriesT = -Infinity;
    this.blankUntil = -1;
    this.lastUpdate = null;
    this.session = {
      id: `run-${Date.now().toString(36)}`,
      startedAt: Date.now(),
      kind,
      mic: source.label,
      zone: { low: s.zoneLow, high: s.zoneHigh },
      breathMode: s.breathMode,
      series: [], // [seconds, breaths/min | null, state code]
      cues: [], // [seconds, type, breaths/min]
      cadence: [],
    };
    this._attach();
    this.pipeline.start();
    this._setStatus('running');
    this.feedback.cue({ type: 'start', zoneLow: s.zoneLow, zoneHigh: s.zoneHigh, rate: null });
    if (s.keepAwake) this.wakeLock.acquire();
  }

  _attach() {
    const s = this.settings.get();
    if (this.pipeline) this.pipeline.paused = true;
    const p = new Pipeline(this.source, { mode: s.breathMode, withCurve: true, keepAudioSec: this.kind === 'live' ? 30 : 0 });
    p.addEventListener('frame', (e) => emit(this, 'frame', e.detail));
    p.addEventListener('estimate', (e) => this._onEstimate(e.detail));
    p.addEventListener('ended', () => this._onMicEnded());
    this.pipeline = p;
  }

  _onEstimate({ est, cadence }) {
    if (this.status !== 'running') return;
    const t = est.t + this.timeOffset;
    this.lastT = t;
    // While a cue plays through a phone speaker the chest mic hears it, so
    // readings that overlap a cue are not trusted.
    const blanked = this.kind === 'live' && t < this.blankUntil;
    const res = this.coach.update({ ...est, t, valid: est.valid && !blanked });
    for (const cue of res.cues) this._cue(cue);
    if (t - this.lastSeriesT >= 5) {
      this.lastSeriesT = t;
      this.session.series.push([Math.round(t), res.rate === null ? null : Math.round(res.rate * 10) / 10, STATE_CODES[res.state]]);
      if (cadence.valid) this.session.cadence.push([Math.round(t), Math.round(cadence.spm)]);
    }
    this.lastUpdate = { t, est, coach: res, cadence, summary: this.coach.summary(), blanked };
    emit(this, 'update', this.lastUpdate);
  }

  _cue(cue) {
    this.session.cues.push([Math.round(cue.t), cue.type, cue.rate]);
    this.feedback.cue(cue);
    if (this.kind === 'live' && this.feedback.audible) this.blankUntil = cue.t + 6;
    emit(this, 'cue', cue);
  }

  _onMicEnded() {
    if (!this.running) return;
    this.feedback.say('Microphone disconnected.');
    emit(this, 'error', { message: 'The microphone was disconnected. Plug it back in and start again.' });
    this.stop();
  }

  pause() {
    if (this.status !== 'running') return;
    this.pipeline.paused = true;
    this._setStatus('paused');
  }

  resume() {
    if (this.status !== 'paused') return;
    // Fresh detector so the pause doesn't leave a seam in its history; the
    // coach keeps going on a continuous clock.
    this.timeOffset = this.lastT;
    this._attach();
    this._setStatus('running');
  }

  /** Stop and save. Returns the saved run (or null if it was too short). */
  stop() {
    if (!this.running) return null;
    this.pipeline.paused = true;
    this.pipeline.stop();
    this.wakeLock.release();
    const sum = this.coach.summary();
    const valid = this.session.series.filter((r) => r[1] !== null).map((r) => r[1]);
    const run = {
      ...this.session,
      durationSec: Math.round(this.lastT),
      avgRate: valid.length ? Math.round((valid.reduce((a, b) => a + b, 0) / valid.length) * 10) / 10 : null,
      maxRate: valid.length ? Math.max(...valid) : null,
      inZoneShare: sum.inZoneShare,
      seconds: sum.seconds,
      zone: { low: this.coach.o.zoneLow, high: this.coach.o.zoneHigh },
    };
    const saved = run.durationSec >= 30 && run.kind === 'live' ? history.add(run) : false;
    this.lastRun = run;
    this._setStatus('idle');
    emit(this, 'stopped', { run, saved });
    return run;
  }

  applySettings() {
    if (!this.running) return;
    const s = this.settings.get();
    this.coach.setOptions(coachOptions(s));
    this.pipeline.detector.setOptions({ mode: s.breathMode });
  }

  /** Suggest a zone centred on the breathing of the last minute. */
  learnZone() {
    if (!this.coach) return null;
    const m = this.coach.recentMedian(60, 20);
    if (m === null) return null;
    const half = Math.max(2, Math.round(m * 0.08));
    const mid = Math.round(m);
    return { low: mid - half, high: mid + half, median: m };
  }

  recentAudio() {
    return this.pipeline && this.pipeline.recent;
  }
}
