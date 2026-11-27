// Periodicity analysis helpers: detrending, normalised cross-correlation
// (NCCF) and peak picking with parabolic interpolation.

/** Remove the least-squares straight line from x. */
export function detrend(x, out = new Float64Array(x.length)) {
  const n = x.length;
  if (!n) return out;
  let sum = 0;
  for (let i = 0; i < n; i++) sum += x[i];
  const mean = sum / n;
  const mid = (n - 1) / 2;
  let sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) {
    const d = i - mid;
    sxy += d * (x[i] - mean);
    sxx += d * d;
  }
  const slope = sxx > 0 ? sxy / sxx : 0;
  for (let i = 0; i < n; i++) out[i] = x[i] - mean - slope * (i - mid);
  return out;
}

/**
 * Normalised cross-correlation between the newest `n` samples of `x` and the
 * equally long segment `lag` samples earlier, for lag = 0..maxLag:
 *
 *   r(lag) = Σ x[i]·x[i-lag] / sqrt(Σ x[i]² · Σ x[i-lag]²)
 *
 * Unlike a plain autocorrelation it is not biased towards short lags, and it
 * is invariant to the signal's gain. Requires x.length >= n + maxLag.
 */
export function nccf(x, n, maxLag, out = new Float64Array(maxLag + 1)) {
  const L = x.length;
  const start = L - n;
  if (start - maxLag < 0) throw new RangeError('nccf: not enough samples for maxLag');
  let eRef = 0;
  for (let i = start; i < L; i++) eRef += x[i] * x[i];
  let eLag = eRef;
  for (let lag = 0; lag <= maxLag; lag++) {
    if (lag > 0) {
      const add = x[start - lag];
      const drop = x[L - lag];
      eLag += add * add - drop * drop;
    }
    let num = 0;
    for (let i = start; i < L; i++) num += x[i] * x[i - lag];
    const den = Math.sqrt(eRef * Math.max(eLag, 0));
    out[lag] = den > 1e-18 ? num / den : 0;
  }
  return out;
}

/**
 * NCCF where the reference segment x[refStart, refStart + n) and every lagged
 * segment x[refStart - lag, refStart - lag + n) each have their own
 * least-squares line removed before correlating. A level step or slow drift
 * elsewhere in the buffer (breathing stopping, a car passing) then cannot
 * masquerade as periodicity. Requires refStart >= maxLag.
 */
export function nccfDetrended(x, refStart, n, maxLag, out = new Float64Array(maxLag + 1)) {
  if (refStart - maxLag < 0 || refStart + n > x.length) throw new RangeError('nccfDetrended: segment out of range');
  const mid = (n - 1) / 2;
  let sxx = 0;
  for (let i = 0; i < n; i++) sxx += (i - mid) * (i - mid);
  let s0 = 0, s1 = 0;
  for (let i = 0; i < n; i++) {
    const v = x[refStart + i];
    s0 += v;
    s1 += (i - mid) * v;
  }
  const ma = s0 / n;
  const sa = sxx > 0 ? s1 / sxx : 0;
  const a = new Float64Array(n);
  let ea = 0;
  for (let i = 0; i < n; i++) {
    const d = x[refStart + i] - ma - sa * (i - mid);
    a[i] = d;
    ea += d * d;
  }
  for (let lag = 0; lag <= maxLag; lag++) {
    const bs = refStart - lag;
    // a is orthogonal to constants and to the ramp, so correlating it with
    // the raw lagged segment equals correlating it with the detrended one.
    let num = 0, b0 = 0, b1 = 0, b2 = 0;
    for (let i = 0; i < n; i++) {
      const v = x[bs + i];
      num += a[i] * v;
      b0 += v;
      b1 += (i - mid) * v;
      b2 += v * v;
    }
    const eb = b2 - (b0 * b0) / n - (sxx > 0 ? (b1 * b1) / sxx : 0);
    out[lag] = ea > 1e-18 && eb > 1e-18 ? num / Math.sqrt(ea * eb) : 0;
  }
  return out;
}

/**
 * Local maxima of r within [lo, hi] (inclusive), refined with a parabola
 * through the three samples around each maximum.
 * @returns {{lag: number, value: number, index: number}[]}
 */
export function findPeaks(r, lo, hi, minValue = -Infinity) {
  const peaks = [];
  const a = Math.max(1, Math.ceil(lo));
  const b = Math.min(r.length - 2, Math.floor(hi));
  for (let i = a; i <= b; i++) {
    const y0 = r[i - 1], y1 = r[i], y2 = r[i + 1];
    if (y1 > y0 && y1 >= y2 && y1 >= minValue) {
      const den = y0 - 2 * y1 + y2;
      let d = den !== 0 ? (0.5 * (y0 - y2)) / den : 0;
      if (d > 0.5) d = 0.5;
      else if (d < -0.5) d = -0.5;
      peaks.push({ lag: i + d, value: y1 - 0.25 * (y0 - y2) * d, index: i });
    }
  }
  return peaks;
}

/** Linearly interpolated value of r at a fractional lag (clamped to range). */
export function valueAt(r, lag) {
  if (lag <= 0) return r[0];
  const last = r.length - 1;
  if (lag >= last) return r[last];
  const i = Math.floor(lag);
  const f = lag - i;
  return r[i] * (1 - f) + r[i + 1] * f;
}

/** Median of an array of numbers (copy; input untouched). */
export function median(values) {
  const n = values.length;
  if (!n) return NaN;
  const s = Array.from(values).sort((p, q) => p - q);
  return n % 2 ? s[(n - 1) / 2] : 0.5 * (s[n / 2 - 1] + s[n / 2]);
}
