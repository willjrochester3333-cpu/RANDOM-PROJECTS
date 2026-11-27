// Biquad IIR filters (RBJ "Audio EQ Cookbook" designs), transposed direct
// form II with float64 state. Pure JS so the exact same code runs in the
// browser and in the Node test suite.

const TAU = 2 * Math.PI;

/** 2nd-order low-pass section coefficients, normalised so a0 = 1. */
export function lowpassCoeffs(fc, fs, q = Math.SQRT1_2) {
  const w0 = (TAU * fc) / fs;
  const cos = Math.cos(w0);
  const alpha = Math.sin(w0) / (2 * q);
  const a0 = 1 + alpha;
  const b = (1 - cos) / 2 / a0;
  return { b0: b, b1: (1 - cos) / a0, b2: b, a1: (-2 * cos) / a0, a2: (1 - alpha) / a0 };
}

/** 2nd-order high-pass section coefficients, normalised so a0 = 1. */
export function highpassCoeffs(fc, fs, q = Math.SQRT1_2) {
  const w0 = (TAU * fc) / fs;
  const cos = Math.cos(w0);
  const alpha = Math.sin(w0) / (2 * q);
  const a0 = 1 + alpha;
  const b = (1 + cos) / 2 / a0;
  return { b0: b, b1: -(1 + cos) / a0, b2: b, a1: (-2 * cos) / a0, a2: (1 - alpha) / a0 };
}

/** 2nd-order band-pass (constant 0 dB peak gain) section coefficients. */
export function bandpassCoeffs(fc, fs, q = Math.SQRT1_2) {
  const w0 = (TAU * fc) / fs;
  const cos = Math.cos(w0);
  const alpha = Math.sin(w0) / (2 * q);
  const a0 = 1 + alpha;
  return { b0: alpha / a0, b1: 0, b2: -alpha / a0, a1: (-2 * cos) / a0, a2: (1 - alpha) / a0 };
}

/**
 * Q values of the 2nd-order sections that make up an even-order
 * Butterworth filter: Q_k = 1 / (2 sin((2k - 1)π / 2n)).
 */
export function butterworthQs(order) {
  if (order < 2 || order % 2) throw new Error('Butterworth order must be even and >= 2');
  const qs = [];
  for (let k = 1; k <= order / 2; k++) {
    qs.push(1 / (2 * Math.sin(((2 * k - 1) * Math.PI) / (2 * order))));
  }
  return qs;
}

export class Biquad {
  constructor(c) {
    this.b0 = c.b0; this.b1 = c.b1; this.b2 = c.b2;
    this.a1 = c.a1; this.a2 = c.a2;
    this.s1 = 0; this.s2 = 0;
  }

  /** DC gain H(z = 1). */
  dcGain() {
    return (this.b0 + this.b1 + this.b2) / (1 + this.a1 + this.a2);
  }

  /**
   * Put the filter in the steady state it would reach after an infinitely
   * long constant input x0, so there is no start-up transient.
   */
  reset(x0 = 0) {
    const y = x0 * this.dcGain();
    this.s2 = this.b2 * x0 - this.a2 * y;
    this.s1 = y - this.b0 * x0;
  }

  step(x) {
    const y = this.b0 * x + this.s1;
    this.s1 = this.b1 * x - this.a1 * y + this.s2;
    this.s2 = this.b2 * x - this.a2 * y;
    return y;
  }

  /** Filter `input` into `output` (may be the same array). */
  process(input, output = input, n = input.length) {
    const { b0, b1, b2, a1, a2 } = this;
    let s1 = this.s1, s2 = this.s2;
    for (let i = 0; i < n; i++) {
      const x = input[i];
      const y = b0 * x + s1;
      s1 = b1 * x - a1 * y + s2;
      s2 = b2 * x - a2 * y;
      output[i] = y;
    }
    this.s1 = s1; this.s2 = s2;
    return output;
  }
}

/** A chain of biquads applied in series. */
export class Cascade {
  constructor(sections) {
    this.sections = sections;
  }

  reset(x0 = 0) {
    let x = x0;
    for (const s of this.sections) {
      s.reset(x);
      x *= s.dcGain();
    }
  }

  step(x) {
    for (const s of this.sections) x = s.step(x);
    return x;
  }

  process(input, output = input, n = input.length) {
    let src = input;
    for (const s of this.sections) {
      s.process(src, output, n);
      src = output;
    }
    return output;
  }

  /** Magnitude response at frequency f (Hz) for sample rate fs. */
  magnitudeAt(f, fs) {
    const w = (TAU * f) / fs;
    let mag = 1;
    for (const s of this.sections) {
      // H(e^jw) = (b0 + b1 e^-jw + b2 e^-2jw) / (1 + a1 e^-jw + a2 e^-2jw)
      const c1 = Math.cos(w), s1 = Math.sin(w), c2 = Math.cos(2 * w), s2 = Math.sin(2 * w);
      const nr = s.b0 + s.b1 * c1 + s.b2 * c2, ni = -(s.b1 * s1 + s.b2 * s2);
      const dr = 1 + s.a1 * c1 + s.a2 * c2, di = -(s.a1 * s1 + s.a2 * s2);
      mag *= Math.hypot(nr, ni) / Math.hypot(dr, di);
    }
    return mag;
  }
}

export function butterworthLowpass(order, fc, fs) {
  return new Cascade(butterworthQs(order).map((q) => new Biquad(lowpassCoeffs(fc, fs, q))));
}

export function butterworthHighpass(order, fc, fs) {
  return new Cascade(butterworthQs(order).map((q) => new Biquad(highpassCoeffs(fc, fs, q))));
}

/** Band-pass built from a Butterworth high-pass followed by a low-pass. */
export function butterworthBandpass(lo, hi, fs, hpOrder = 4, lpOrder = 2) {
  return new Cascade([
    ...butterworthHighpass(hpOrder, lo, fs).sections,
    ...butterworthLowpass(lpOrder, hi, fs).sections,
  ]);
}
