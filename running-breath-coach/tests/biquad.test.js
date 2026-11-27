import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  butterworthQs, butterworthLowpass, butterworthHighpass, butterworthBandpass, Biquad, lowpassCoeffs,
} from '../app/js/dsp/biquad.js';
import { RingBuffer } from '../app/js/dsp/ring-buffer.js';
import { detrend, nccf, nccfDetrended, findPeaks, median } from '../app/js/dsp/periodicity.js';

const close = (a, b, eps, msg) => assert.ok(Math.abs(a - b) <= eps, `${msg ?? ''} expected ${b}, got ${a}`);

test('Butterworth section Qs match the textbook values', () => {
  close(butterworthQs(2)[0], Math.SQRT1_2, 1e-12);
  const q4 = butterworthQs(4);
  close(q4[0], 1.30656, 1e-4);
  close(q4[1], 0.54120, 1e-4);
  const q6 = butterworthQs(6);
  close(q6[0], 1.93185, 1e-4);
  close(q6[1], 0.70711, 1e-4);
  close(q6[2], 0.51764, 1e-4);
});

test('low-pass is -3 dB at cutoff, unity at DC, and rolls off at 6n dB/octave', () => {
  const fs = 48000;
  const lp = butterworthLowpass(4, 1000, fs);
  close(20 * Math.log10(lp.magnitudeAt(1000, fs)), -3.01, 0.05, 'cutoff');
  close(lp.magnitudeAt(1, fs), 1, 1e-6, 'DC');
  // one octave above cutoff a 4th-order Butterworth is ~ -24.1 dB
  close(20 * Math.log10(lp.magnitudeAt(2000, fs)), -24.1, 0.5, 'octave');
});

test('high-pass blocks DC and passes high frequencies', () => {
  const fs = 48000;
  const hp = butterworthHighpass(4, 200, fs);
  assert.ok(hp.magnitudeAt(5, fs) < 1e-5);
  close(hp.magnitudeAt(5000, fs), 1, 1e-3);
  close(20 * Math.log10(hp.magnitudeAt(200, fs)), -3.01, 0.05);
});

test('band-pass peaks inside its band', () => {
  const fs = 48000;
  const bp = butterworthBandpass(400, 1000, fs, 4, 2);
  const mid = bp.magnitudeAt(630, fs);
  assert.ok(mid > 0.8, `mid-band gain ${mid}`);
  assert.ok(bp.magnitudeAt(100, fs) < 0.05 * mid);
  assert.ok(bp.magnitudeAt(8000, fs) < 0.05 * mid);
});

test('steady-state reset removes the start-up transient', () => {
  const lp = butterworthLowpass(6, 1.5, 25);
  lp.reset(-60);
  for (let i = 0; i < 50; i++) close(lp.step(-60), -60, 1e-9, `sample ${i}`);
  const b = new Biquad(lowpassCoeffs(100, 8000));
  b.reset(2);
  close(b.step(2), 2, 1e-12);
});

test('block and per-sample processing agree', () => {
  const a = butterworthBandpass(300, 3000, 16000);
  const b = butterworthBandpass(300, 3000, 16000);
  const x = Float64Array.from({ length: 1000 }, (_, i) => Math.sin(i * 0.37) + Math.cos(i * 1.9));
  const y = a.process(x, new Float64Array(1000));
  for (let i = 0; i < 1000; i++) close(y[i], b.step(x[i]), 1e-12);
});

test('ring buffer returns the newest values oldest-first across the wrap', () => {
  const r = new RingBuffer(5);
  for (let i = 1; i <= 8; i++) r.push(i);
  assert.deepEqual(Array.from(r.latest()), [4, 5, 6, 7, 8]);
  assert.deepEqual(Array.from(r.latest(3)), [6, 7, 8]);
  assert.equal(r.get(0), 8);
  assert.equal(r.get(4), 4);
});

test('NCCF finds the period of a sinusoid and ignores a level step', () => {
  const period = 37;
  const x = Float64Array.from({ length: 600 }, (_, i) => Math.sin((2 * Math.PI * i) / period));
  const r = nccf(detrend(x), 400, 150);
  const peaks = findPeaks(r, 20, 150);
  close(peaks[0].lag, period, 0.2);
  assert.ok(peaks[0].value > 0.99);

  // Pure noise followed by a big level drop: the detrended variant must not
  // report strong periodicity.
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) - 0.5;
  const y = Float64Array.from({ length: 400 }, (_, i) => (i < 120 ? 30 : 0) + rnd());
  const rd = nccfDetrended(y, 150, 250, 150);
  const strongest = Math.max(...findPeaks(rd, 20, 149).map((p) => p.value), 0);
  assert.ok(strongest < 0.5, `spurious periodicity ${strongest}`);
});

test('median', () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([4, 1, 3, 2]), 2.5);
  assert.ok(Number.isNaN(median([])));
});
