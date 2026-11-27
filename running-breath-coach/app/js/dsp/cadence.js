// Step cadence from the "impact" signal that the front end's median filter
// strips out: every footstrike is a short broadband thump on a chest mic.

import { butterworthLowpass } from './biquad.js';
import { RingBuffer } from './ring-buffer.js';
import { nccf, findPeaks, detrend } from './periodicity.js';

export const CADENCE_DEFAULTS = {
  minSpm: 120,
  maxSpm: 230,
  windowSec: 6,
  // With no footsteps at all, noise reaches ~0.21; real steps that are up to
  // ~8 dB quieter than the breathing still score above this.
  minConfidence: 0.22,
  stableCount: 3, // consecutive picks that must agree within 5%
};

export class CadenceDetector {
  constructor(subRate, options = {}) {
    this.opts = { ...CADENCE_DEFAULTS, ...options };
    this.rate = subRate;
    this.minLag = Math.floor((subRate * 60) / this.opts.maxSpm);
    this.maxLag = Math.ceil((subRate * 60) / this.opts.minSpm);
    this.n = Math.round(this.opts.windowSec * subRate);
    this.hist = new RingBuffer(this.n + this.maxLag + 2);
    // Smooth the spiky impact train so footstrikes with a few ms of timing
    // jitter still line up in the correlation.
    this.smooth = butterworthLowpass(2, 10, subRate);
    this.recent = []; // recent confident picks (lags)
    this.buf = new Float64Array(this.n + this.maxLag);
  }

  pushImpacts(values) {
    for (let i = 0; i < values.length; i++) {
      // compress big thumps so one stumble doesn't dominate the window
      this.hist.push(this.smooth.step(Math.sqrt(Math.max(0, values[i]))));
    }
  }

  estimate() {
    const need = this.n + this.maxLag;
    if (this.hist.length < need) return { spm: null, confidence: 0, valid: false };
    const x = detrend(this.hist.latest(need, this.buf));
    const r = nccf(x, this.n, this.maxLag);
    const peaks = findPeaks(r, this.minLag, this.maxLag, 0.05);
    if (!peaks.length) {
      this.recent = [];
      return { spm: null, confidence: 0, valid: false };
    }
    let best = peaks[0];
    for (const p of peaks) if (p.value > best.value) best = p;
    const confident = best.value >= this.opts.minConfidence;
    if (confident) {
      this.recent.push(best.lag);
      if (this.recent.length > this.opts.stableCount) this.recent.shift();
    } else {
      this.recent = [];
    }
    const stable = this.recent.length === this.opts.stableCount &&
      this.recent.every((lag) => Math.abs(lag / best.lag - 1) < 0.05);
    return {
      spm: (60 * this.rate) / best.lag,
      confidence: best.value,
      valid: confident && stable,
    };
  }
}
