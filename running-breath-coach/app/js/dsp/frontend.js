// Audio front end: splits the microphone signal into frequency bands and
// turns each band into a short-time energy sequence that is robust against
// footstrike thumps.
//
//   audio ─┬─ band-pass 150–400 Hz ──┐
//          ├─ band-pass 400–1000 Hz ─┤  energy per 5 ms sub-frame
//          ├─ band-pass 1–2.5 kHz ───┤  → running median (~95 ms)  ← removes
//          ├─ band-pass 2.5–5 kHz ───┘    short impacts, keeps breath bursts
//          │                             → averaged into ~40 ms frames
//          └─ band-pass 40–150 Hz  (impact band: footstrike thumps only)
//
// The energy that the median filter throws away is reported as an "impact"
// signal at the sub-frame rate; the cadence detector uses it to count steps.

import { butterworthBandpass } from './biquad.js';

export const DEFAULT_BANDS = [
  [150, 400],
  [400, 1000],
  [1000, 2500],
  [2500, 5000],
];
export const DEFAULT_IMPACT_BAND = [40, 150];

const EPS = 1e-12;

export class BandEnergyFrontend {
  constructor({
    sampleRate,
    bands = DEFAULT_BANDS,
    impactBand = DEFAULT_IMPACT_BAND,
    subRate = 200, // sub-frames per second (5 ms)
    decimation = 8, // sub-frames per output frame (→ 25 frames/s)
    medianLength = 19, // sub-frames in the impulse-rejecting median (95 ms)
  } = {}) {
    if (!(sampleRate > 0)) throw new Error('sampleRate is required');
    this.sampleRate = sampleRate;
    this.subHop = Math.max(1, Math.round(sampleRate / subRate));
    this.subRate = sampleRate / this.subHop;
    this.decimation = decimation;
    this.frameRate = this.subRate / decimation;

    const nyquist = sampleRate / 2;
    this.bands = [];
    for (const [lo, hi0] of bands) {
      const hi = Math.min(hi0, nyquist * 0.85);
      if (hi > lo * 1.25) this.bands.push([lo, hi]);
    }
    if (!this.bands.length) throw new Error('No usable frequency bands at this sample rate');
    // Breath bands first (indices 0..K-1), then the optional impact band.
    const all = impactBand ? [...this.bands, impactBand] : [...this.bands];
    this.filters = all.map(([lo, hi]) => butterworthBandpass(lo, hi, sampleRate, 4, 2));
    this.K = this.bands.length;
    const KA = (this.KA = all.length);

    this.M = medianLength | 1; // odd length so the median is a real sample
    this.half = (this.M - 1) >> 1;
    this.ring = Array.from({ length: KA }, () => new Float64Array(this.M));
    this.ringPos = 0;
    this.ringFill = 0;
    this.sortBuf = new Float64Array(this.M);

    this.subAcc = new Float64Array(KA);
    this.rawAcc = 0;
    this.subCount = 0; // samples in the current partial sub-frame
    this.subEnergy = Array.from({ length: KA }, () => new Float64Array(64));
    this.subRaw = new Float64Array(64);

    this.frameAcc = new Float64Array(this.K);
    this.frameRaw = 0;
    this.frameSubs = 0;
    this.impact = new Float64Array(decimation);
    this.slow = new Float64Array(KA);
    this.slowAlpha = 1 / (2 * this.subRate);
    this.peak = 0;
    this.scratch = new Float64Array(0);

    /** @type {null | ((frame: {energy: Float64Array, impact: Float64Array, levelDb: number, peak: number}) => void)} */
    this.onFrame = null;
  }

  /** Feed mono audio samples (any length). Emits frames through onFrame. */
  process(samples) {
    const n = samples.length;
    if (!n) return;
    const hop = this.subHop;
    const KA = this.KA;
    const start = this.subCount;
    const nSub = Math.floor((start + n) / hop);

    if (this.scratch.length < n) this.scratch = new Float64Array(n);
    if (this.subRaw.length < nSub) {
      const len = nSub * 2;
      this.subRaw = new Float64Array(len);
      this.subEnergy = Array.from({ length: KA }, () => new Float64Array(len));
    }

    // Broadband level + peak (for the level meter and clipping warning).
    {
      let acc = this.rawAcc, cnt = start, j = 0, peak = this.peak;
      for (let i = 0; i < n; i++) {
        const x = samples[i];
        acc += x * x;
        const ax = x < 0 ? -x : x;
        if (ax > peak) peak = ax;
        if (++cnt === hop) { this.subRaw[j++] = acc / hop; acc = 0; cnt = 0; }
      }
      this.rawAcc = acc;
      this.peak = peak;
    }

    // Band energies per completed sub-frame.
    const y = this.scratch;
    for (let k = 0; k < KA; k++) {
      this.filters[k].process(samples, y, n);
      const out = this.subEnergy[k];
      let acc = this.subAcc[k], cnt = start, j = 0;
      for (let i = 0; i < n; i++) {
        const v = y[i];
        acc += v * v;
        if (++cnt === hop) { out[j++] = acc / hop; acc = 0; cnt = 0; }
      }
      this.subAcc[k] = acc;
    }
    this.subCount = (start + n) % hop;

    for (let j = 0; j < nSub; j++) this._pushSubFrame(j);
  }

  _pushSubFrame(j) {
    const K = this.K, KA = this.KA, M = this.M;
    const pos = this.ringPos;
    for (let k = 0; k < KA; k++) this.ring[k][pos] = this.subEnergy[k][j];
    this.ringPos = (pos + 1) % M;
    if (this.ringFill < M) this.ringFill++;

    const fill = this.ringFill;
    // Index of the sub-frame at the centre of the median window.
    const centre = (pos - Math.min(this.half, (fill - 1) >> 1) + M) % M;
    let impact = 0;
    for (let k = 0; k < KA; k++) {
      const med = this._median(this.ring[k], fill);
      if (k < K) this.frameAcc[k] += med;
      // Slow (~2 s) average of the band level. A floor relative to it keeps
      // a thump in a quiet gap between breaths from scoring 100 dB while the
      // same thump during a breath scores 3 dB, which would bury the step
      // rhythm under the breathing rhythm.
      const raw = this.ring[k][centre];
      this.slow[k] += (raw - this.slow[k]) * this.slowAlpha;
      const floor = 0.05 * this.slow[k] + EPS;
      const ratio = (raw + floor) / (med + floor);
      if (ratio > 1) impact += 10 * Math.log10(ratio);
    }
    this.impact[this.frameSubs] = impact;
    this.frameRaw += this.subRaw[j];

    if (++this.frameSubs === this.decimation) {
      const d = this.decimation;
      const energy = new Float64Array(K);
      for (let k = 0; k < K; k++) { energy[k] = this.frameAcc[k] / d; this.frameAcc[k] = 0; }
      const rms = Math.sqrt(this.frameRaw / d);
      const frame = {
        energy,
        impact: this.impact.slice(),
        levelDb: 20 * Math.log10(rms + 1e-9),
        peak: this.peak,
      };
      this.frameRaw = 0;
      this.frameSubs = 0;
      this.peak = 0;
      if (this.onFrame) this.onFrame(frame);
    }
  }

  _median(ring, fill) {
    const b = this.sortBuf;
    if (fill === this.M) {
      for (let i = 0; i < fill; i++) b[i] = ring[i];
    } else {
      // Ring not yet full: valid values are the `fill` most recent ones.
      for (let i = 0; i < fill; i++) b[i] = ring[(this.ringPos - 1 - i + this.M) % this.M];
    }
    // Insertion sort; fill <= ~21 so this is cheap.
    for (let i = 1; i < fill; i++) {
      const v = b[i];
      let p = i - 1;
      while (p >= 0 && b[p] > v) { b[p + 1] = b[p]; p--; }
      b[p + 1] = v;
    }
    return b[fill >> 1];
  }
}
