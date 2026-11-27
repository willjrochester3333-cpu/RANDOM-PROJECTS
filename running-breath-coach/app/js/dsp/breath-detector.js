// Breathing-rate estimator.
//
// 1. BandEnergyFrontend → per-band energies at ~25 frames/s, with footstrike
//    impulses removed by a median filter.
// 2. Each band becomes a log-energy envelope (dB, so mic gain doesn't matter),
//    low-passed at ~1.6 Hz so step-rate ripple (2.5–3.2 Hz) is suppressed.
//    One extra "tilt" channel (high bands minus low bands) follows spectral
//    shape, which tells hissy inhales apart from breathy exhales.
// 3. Once a second, every channel's normalised cross-correlation (NCCF) over
//    the last ~10 s is computed, channels are weighted by how periodic they
//    are, and the weighted sum is searched for the breathing period. A
//    tracking penalty keeps the estimate from hopping between harmonics.

import { BandEnergyFrontend } from './frontend.js';
import { butterworthLowpass } from './biquad.js';
import { RingBuffer } from './ring-buffer.js';
import { nccfDetrended, findPeaks, valueAt } from './periodicity.js';

export const DETECTOR_DEFAULTS = {
  minBpm: 10,
  maxBpm: 75,
  windowSec: 10, // reference window for the correlation
  minWindowSec: 6, // shorter window used while the history fills up
  updateSec: 1,
  // 'auto'   – one breath per periodic sound pattern (handles quiet inhales,
  //            and loud inhales that sound different from exhales)
  // 'double' – inhale and exhale sound alike: two bursts make one breath
  mode: 'auto',
  minConfidence: 0.42,
  switchRatio: 0.88, // a shorter period must reach this share of the best peak…
  keepRatio: 0.75, // …or this share if it is where the estimate already is
  consistency: 0.15, // max relative change between updates to count as stable
};

const LOG_FLOOR = 1e-12;

export class BreathDetector {
  constructor(sampleRate, options = {}) {
    const { frontend: frontendOptions, ...rest } = options;
    this.opts = { ...DETECTOR_DEFAULTS, ...rest };
    this.frontend = new BandEnergyFrontend({ sampleRate, ...(frontendOptions || {}) });
    this.frontend.onFrame = (f) => this._onFrame(f);
    this.envRate = this.frontend.frameRate;
    this.bandCount = this.frontend.K;
    // Channels: one per band + one spectral-tilt channel (needs >= 2 bands).
    this.channelCount = this.bandCount + (this.bandCount >= 2 ? 1 : 0);
    this._configure();
    this.frameCount = 0;
    this.lastEstimate = null;
    /** @type {null | ((frame: object) => void)} */
    this.onFrame = null;
    /** @type {null | ((estimate: object) => void)} */
    this.onEstimate = null;
    /** @type {null | ((frame: object) => void)} raw front-end frames (cadence) */
    this.onFrontendFrame = null;
  }

  _configure() {
    const o = this.opts;
    const rate = this.envRate;
    this.minLag = Math.max(2, Math.floor((rate * 60) / o.maxBpm));
    this.maxLag = Math.ceil((rate * 60) / o.minBpm);
    this.nMax = Math.round(o.windowSec * rate);
    this.nMin = Math.round(o.minWindowSec * rate);
    this.histLen = this.nMax + this.maxLag + 2;
    const cutoff = Math.min(rate * 0.4, (1.25 * o.maxBpm) / 60);
    this.envFilters = Array.from({ length: this.channelCount }, () => butterworthLowpass(6, cutoff, rate));
    this.hist = Array.from({ length: this.channelCount }, () => new RingBuffer(this.histLen));
    this.filtersPrimed = false;
    this.updateEvery = Math.max(1, Math.round(o.updateSec * rate));
    this.framesSinceUpdate = 0;
    this.weights = new Float64Array(this.channelCount);
    this.chanMean = new Float64Array(this.channelCount);
    this.chanStd = new Float64Array(this.channelCount).fill(1);
    this.prevLag = null;
    this.prevLagTime = -Infinity;
    this.lastRawLag = null;
    this.activity = 0;
    this.actLo = Infinity;
    this.actHi = -Infinity;
  }

  /** Change mode / range on the fly (e.g. from settings). */
  setOptions(patch) {
    const rangeChanged = ('minBpm' in patch && patch.minBpm !== this.opts.minBpm) ||
      ('maxBpm' in patch && patch.maxBpm !== this.opts.maxBpm) ||
      ('windowSec' in patch && patch.windowSec !== this.opts.windowSec);
    Object.assign(this.opts, patch);
    if (rangeChanged) this._configure();
  }

  get time() {
    return this.frameCount / this.envRate;
  }

  pushAudio(samples) {
    this.frontend.process(samples);
  }

  _onFrame(f) {
    this.frameCount++;
    if (this.onFrontendFrame) this.onFrontendFrame(f);
    const K = this.bandCount;
    const C = this.channelCount;
    const env = new Float64Array(C);
    for (let k = 0; k < K; k++) env[k] = 10 * Math.log10(f.energy[k] + LOG_FLOOR);
    if (C > K) {
      // spectral tilt: mean of the upper half of the bands minus the lower half
      const h = K >> 1;
      let lo = 0, hi = 0;
      for (let k = 0; k < h; k++) lo += env[k];
      for (let k = h; k < K; k++) hi += env[k];
      env[K] = hi / (K - h) - lo / h;
    }
    if (!this.filtersPrimed) {
      for (let c = 0; c < C; c++) this.envFilters[c].reset(env[c]);
      this.filtersPrimed = true;
    }
    let act = 0, wsum = 0;
    for (let c = 0; c < C; c++) {
      const y = this.envFilters[c].step(env[c]);
      this.hist[c].push(y);
      const w = this.weights[c];
      if (w > 0 && c < K) {
        act += (w * (y - this.chanMean[c])) / this.chanStd[c];
        wsum += w;
      }
    }
    // "Activity" drives the breathing animation: weighted z-score of the
    // band envelopes, mapped to 0..1 with slowly adapting bounds.
    if (wsum > 0) act /= wsum;
    else act = (this.hist[1 % K].get(0) - this.chanMean[1 % K]) / 6;
    if (!Number.isFinite(act)) act = 0;
    if (!Number.isFinite(this.actHi)) {
      this.actHi = act + 1e-3;
      this.actLo = act - 1e-3;
    }
    const decay = 1 / (8 * this.envRate);
    this.actHi = Math.max(act, this.actHi - (this.actHi - act) * decay);
    this.actLo = Math.min(act, this.actLo + (act - this.actLo) * decay);
    const span = this.actHi - this.actLo;
    this.activity = span > 1e-6 ? (act - this.actLo) / span : 0;

    if (this.onFrame) {
      this.onFrame({ t: this.time, activity: this.activity, levelDb: f.levelDb, peak: f.peak });
    }
    if (++this.framesSinceUpdate >= this.updateEvery) {
      this.framesSinceUpdate = 0;
      const est = this.estimate({ withCurve: Boolean(this.opts.withCurve) });
      this.lastEstimate = est;
      if (this.onEstimate) this.onEstimate(est);
    }
  }

  /**
   * Analyse the current history. Returns an estimate object; `valid` is true
   * when the rate is trustworthy enough to act on.
   */
  estimate({ withCurve = false } = {}) {
    const t = this.time;
    const C = this.channelCount;
    const avail = this.hist[0].length;
    const base = { t, rate: null, confidence: 0, valid: false, warmingUp: false, weights: Array.from(this.weights), peaks: [] };
    const maxLag = Math.min(this.maxLag, avail - this.nMin);
    if (maxLag < 2 * this.minLag) return { ...base, warmingUp: true };
    const n = Math.min(this.nMax, avail - maxLag);

    // Per-channel NCCF over the whole reference window and over each half of
    // it. The halves catch breathing that starts or stops inside the window:
    // a real rhythm must show up in both.
    const curves = [];
    let wsum = 0;
    const sacf = new Float64Array(maxLag + 1);
    const sacfA = new Float64Array(maxLag + 1);
    const sacfB = new Float64Array(maxLag + 1);
    const x = new Float64Array(n + maxLag);
    const halfA = n >> 1;
    for (let c = 0; c < C; c++) {
      this.hist[c].latest(n + maxLag, x);
      // Channel stats over the analysis window (for the activity display).
      let m = 0;
      for (let i = 0; i < x.length; i++) m += x[i];
      m /= x.length;
      let v = 0;
      for (let i = 0; i < x.length; i++) {
        x[i] -= m;
        v += x[i] * x[i];
      }
      this.chanMean[c] = m;
      this.chanStd[c] = Math.sqrt(v / x.length) || 1;

      const r = nccfDetrended(x, maxLag, n, maxLag);
      let q = 0;
      for (let lag = this.minLag; lag <= maxLag; lag++) if (r[lag] > q) q = r[lag];
      // Flat channels (digital silence, or a band the mic can't hear) carry no information.
      const w = this.chanStd[c] > 0.05 && q > 0.2 ? q * q : 0;
      this.weights[c] = w;
      wsum += w;
      curves.push(w ? [r, nccfDetrended(x, maxLag, halfA, maxLag), nccfDetrended(x, maxLag + halfA, n - halfA, maxLag)] : null);
    }
    base.weights = Array.from(this.weights);
    if (wsum <= 0) {
      this.lastRawLag = null;
      return base;
    }
    for (let c = 0; c < C; c++) {
      const w = this.weights[c];
      if (!w) continue;
      const [r, rA, rB] = curves[c];
      for (let lag = 0; lag <= maxLag; lag++) {
        sacf[lag] += (w * r[lag]) / wsum;
        sacfA[lag] += (w * rA[lag]) / wsum;
        sacfB[lag] += (w * rB[lag]) / wsum;
      }
    }

    const peaks = findPeaks(sacf, this.minLag, maxLag, 0.1);
    const toBpm = (lag) => (60 * this.envRate) / lag;
    base.peaks = peaks.map((p) => ({ bpm: toBpm(p.lag), value: p.value }));
    if (withCurve) base.curve = sacf;
    if (!peaks.length) {
      this.lastRawLag = null;
      return base;
    }

    // A periodic signal correlates equally well at every multiple of its
    // period, so the strongest peak is not reliable on its own. Take the
    // shortest-period peak that is nearly as strong as the best one (the
    // classic fix for octave errors in pitch tracking), with hysteresis:
    // a peak near the previous estimate needs less to stay selected.
    const tracking = this.prevLag !== null && t - this.prevLagTime < 10;
    let rMax = 0;
    for (const p of peaks) if (p.value > rMax) rMax = p.value;
    let best = null;
    for (const p of peaks) {
      const near = tracking && Math.abs(Math.log(p.lag / this.prevLag)) < 0.1;
      const threshold = (near ? this.opts.keepRatio : this.opts.switchRatio) * rMax;
      if (p.value >= threshold) { best = p; break; }
    }

    let lag = best.lag;
    // Confidence: periodicity over the whole window, capped by the weaker
    // half so a rhythm that only fills part of the window scores low.
    const halfMin = Math.min(valueAt(sacfA, best.lag), valueAt(sacfB, best.lag));
    const confidence = Math.max(0, Math.min(best.value, 0.5 * (best.value + halfMin)));
    if (this.opts.mode === 'double') {
      // If there is no burst half-way through this period, the period we
      // found is only one of the two breath sounds: a full breath is twice it.
      if (valueAt(sacf, lag / 2) < 0.15 && lag * 2 <= this.maxLag * 1.05) lag *= 2;
    }

    const rate = toBpm(lag);
    // Stability: the previous raw pick should agree with this one.
    const stable = this.lastRawLag !== null && Math.abs(lag / this.lastRawLag - 1) <= this.opts.consistency;
    this.lastRawLag = lag;
    const valid = confidence >= this.opts.minConfidence && stable;
    if (confidence >= this.opts.minConfidence) {
      this.prevLag = best.lag;
      this.prevLagTime = t;
    }
    return { ...base, rate, lag, period: lag / this.envRate, confidence, valid };
  }
}
