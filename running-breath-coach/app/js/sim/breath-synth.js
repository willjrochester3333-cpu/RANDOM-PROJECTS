// Synthetic "chest microphone while running" audio: breath bursts (exhale +
// optional inhale), footstrike thumps, background noise and wind. Used by the
// test suite and by the app's demo mode. Fully deterministic for a given seed.

import { butterworthBandpass, butterworthLowpass, butterworthHighpass } from '../dsp/biquad.js';

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const asFn = (v) => (typeof v === 'function' ? v : () => v);

export const SYNTH_DEFAULTS = {
  seed: 1,
  bpm: 30, // breaths per minute: number or (tSeconds) => number
  breathLevel: 0.2, // exhale peak amplitude: number or (t) => number
  inhaleLevel: 0.35, // inhale amplitude relative to exhale (0 = silent)
  inhaleSound: 'hiss', // 'hiss' (spectrally different) | 'same' (worst case)
  exhaleJet: 0.5, // low-frequency air-jet component on exhales
  inhaleFraction: 0.42, // share of the cycle spent inhaling
  jitter: 0.06, // ± relative breath-to-breath period jitter
  ampJitter: 0.15,
  spm: 170, // steps per minute: number, (t) => number, or 0 for none
  stepLevel: 0.5, // footstrike thump amplitude
  stepsPerBreath: 0, // >0 locks breathing to the step rhythm (e.g. 4 = 2:2)
  noiseLevel: 0.004, // background noise RMS
  windLevel: 0, // low-frequency wind noise RMS
  silences: [], // [[t0, t1], ...] intervals with no breathing
};

export class BreathSynth {
  constructor(sampleRate, options = {}) {
    this.fs = sampleRate;
    this.o = { ...SYNTH_DEFAULTS, ...options };
    this.rand = mulberry32(this.o.seed);
    this.bpm = asFn(this.o.bpm);
    this.spm = asFn(this.o.spm);
    this.level = asFn(this.o.breathLevel);
    const fs = sampleRate;
    const nyq = fs / 2;
    const cap = (f) => Math.min(f, nyq * 0.9);
    this.fExhale = butterworthBandpass(300, cap(2500), fs, 2, 2);
    this.fJet = butterworthLowpass(2, 300, fs);
    this.fInhale = this.o.inhaleSound === 'same'
      ? butterworthBandpass(300, cap(2500), fs, 2, 2)
      : butterworthBandpass(900, cap(5000), fs, 2, 2);
    this.fNoise = butterworthLowpass(2, cap(3000), fs);
    this.fWind = butterworthLowpass(2, 150, fs);
    this.fClick = butterworthHighpass(2, 800, fs);
    this.t = 0; // samples rendered
    this.phase = 0; // breath phase 0..1
    this.cycleScale = 1;
    this.cycleAmp = 1;
    this.stepPhase = 0;
    this.stepCount = 0;
    this.stepScale = 1;
    this.thumps = []; // active footstrikes: {age, amp, freq}
    this.windPhase = this.rand() * Math.PI * 2;
    this._newCycle();
  }

  _newCycle() {
    const j = this.o.jitter;
    this.cycleScale = 1 + (this.rand() * 2 - 1) * j;
    this.cycleAmp = 1 + (this.rand() * 2 - 1) * this.o.ampJitter;
  }

  _inSilence(sec) {
    for (const [a, b] of this.o.silences) if (sec >= a && sec < b) return true;
    return false;
  }

  /** Breath sound envelope for exhale and inhale at breath phase p. */
  _envelopes(p) {
    const fi = this.o.inhaleFraction;
    let inh = 0, exh = 0;
    // inhale: [0, fi)   exhale: [fi + 0.04, 0.96)
    if (p < fi) {
      const u = p / fi;
      inh = Math.sin(Math.PI * u) ** 2;
    } else {
      const a = fi + 0.04, b = 0.96;
      if (p >= a && p < b) {
        const u = (p - a) / (b - a);
        // quicker attack, longer tail, like a forced exhale
        exh = u < 0.35 ? Math.sin((Math.PI / 2) * (u / 0.35)) ** 2 : Math.cos((Math.PI / 2) * ((u - 0.35) / 0.65)) ** 2;
      }
    }
    return [inh, exh];
  }

  render(n) {
    const out = new Float32Array(n);
    const fs = this.fs;
    const o = this.o;
    const rnd = this.rand;
    for (let i = 0; i < n; i++, this.t++) {
      const sec = this.t / fs;

      // --- footsteps ---------------------------------------------------
      const spm = this.spm(sec);
      if (spm > 0) {
        this.stepPhase += spm / 60 / fs / this.stepScale;
        if (this.stepPhase >= 1) {
          this.stepPhase -= 1;
          this.stepCount++;
          this.stepScale = 1 + (rnd() * 2 - 1) * 0.02;
          const lr = this.stepCount % 2 ? 1 : 0.85; // slight left/right asymmetry
          this.thumps.push({ age: 0, amp: o.stepLevel * lr * (0.85 + 0.3 * rnd()), freq: 70 + 30 * rnd() });
        }
      }

      // --- breathing phase ---------------------------------------------
      let p;
      if (o.stepsPerBreath > 0 && spm > 0) {
        p = ((this.stepCount % o.stepsPerBreath) + this.stepPhase) / o.stepsPerBreath;
        if (p < this.phase - 0.5) this._newCycle();
        this.phase = p;
      } else {
        this.phase += this.bpm(sec) / 60 / fs / this.cycleScale;
        if (this.phase >= 1) { this.phase -= 1; this._newCycle(); }
        p = this.phase;
      }

      let s = 0;
      if (!this._inSilence(sec)) {
        const [inh, exh] = this._envelopes(p);
        const lvl = this.level(sec) * this.cycleAmp;
        const w = rnd() * 2 - 1;
        const ex = this.fExhale.step(w) * 3 + this.fJet.step(rnd() * 2 - 1) * 3 * o.exhaleJet;
        const inSound = this.fInhale.step(rnd() * 2 - 1) * 3;
        s += lvl * (exh * ex + inh * o.inhaleLevel * inSound);
      } else {
        // keep filter states moving so there is no click when breathing resumes
        this.fExhale.step(0); this.fJet.step(0); this.fInhale.step(0);
      }

      // --- footstrike thumps -------------------------------------------
      if (this.thumps.length) {
        let click = 0;
        for (let k = this.thumps.length - 1; k >= 0; k--) {
          const th = this.thumps[k];
          const age = th.age / fs;
          s += th.amp * Math.exp(-age / 0.022) * Math.sin(2 * Math.PI * th.freq * age);
          if (age < 0.006) click += th.amp * 0.6 * (rnd() * 2 - 1);
          if (++th.age > fs * 0.15) this.thumps.splice(k, 1);
        }
        s += this.fClick.step(click);
      } else {
        this.fClick.step(0);
      }

      // --- background ----------------------------------------------------
      if (o.noiseLevel > 0) s += o.noiseLevel * 2.2 * this.fNoise.step(rnd() * 2 - 1);
      if (o.windLevel > 0) {
        const gust = 0.6 + 0.4 * Math.sin(2 * Math.PI * 0.13 * sec + this.windPhase);
        s += o.windLevel * 4 * gust * this.fWind.step(rnd() * 2 - 1);
      }
      out[i] = Math.max(-1, Math.min(1, s));
    }
    return out;
  }
}
