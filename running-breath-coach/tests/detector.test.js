import { test } from 'node:test';
import assert from 'node:assert/strict';
import { simulate, score } from './helpers.js';
import { BreathSynth } from '../app/js/sim/breath-synth.js';

const expectAccurate = (s, label, minShare = 0.9) => {
  assert.ok(s.accurateShare >= minShare,
    `${label}: only ${(s.accurateShare * 100).toFixed(0)}% accurate (valid ${(s.validShare * 100).toFixed(0)}%, mean ${s.meanRate?.toFixed(1)})`);
};

test('measures breathing from 15 to 70 breaths/min', () => {
  for (const bpm of [15, 22, 30, 40, 50, 60, 70]) {
    const { estimates } = simulate({ synth: { bpm, spm: 0 } });
    expectAccurate(score(estimates, bpm), `${bpm} bpm`);
  }
});

test('ignores loud footstrikes at running cadence', () => {
  for (const [bpm, spm] of [[24, 160], [36, 172], [48, 182], [60, 190]]) {
    const { estimates } = simulate({ synth: { bpm, spm, stepLevel: 1.5 } });
    expectAccurate(score(estimates, bpm), `${bpm} bpm with ${spm} spm thumps`);
  }
});

test('copes with background noise and wind', () => {
  for (const bpm of [25, 35, 50]) {
    const { estimates } = simulate({ synth: { bpm, noiseLevel: 0.03, windLevel: 0.05 } });
    expectAccurate(score(estimates, bpm), `${bpm} bpm in noise`);
  }
});

test('counts one breath when the inhale is as loud as the exhale but sounds different', () => {
  for (const bpm of [20, 30, 40, 50]) {
    const { estimates } = simulate({ synth: { bpm, inhaleLevel: 1 } });
    expectAccurate(score(estimates, bpm), `${bpm} bpm, loud inhale`);
  }
});

test('"double" mode handles inhales and exhales that sound identical', () => {
  const synth = { inhaleLevel: 1, inhaleSound: 'same', exhaleJet: 0, inhaleFraction: 0.46 };
  for (const bpm of [20, 30, 40, 50]) {
    const { estimates } = simulate({ synth: { ...synth, bpm }, detector: { mode: 'double' } });
    expectAccurate(score(estimates, bpm), `${bpm} bpm identical sounds, double mode`);
  }
});

test('breathing locked to steps (2:2 and 3:3 rhythms)', () => {
  for (const [spm, per, bpm] of [[170, 4, 42.5], [168, 6, 28]]) {
    const { estimates } = simulate({ synth: { bpm, spm, stepsPerBreath: per, stepLevel: 0.8 } });
    expectAccurate(score(estimates, bpm), `${per / 2}:${per / 2} at ${spm} spm`);
  }
});

test('reports nothing when there is no breathing', () => {
  const cases = {
    'noise only': { breathLevel: 0, spm: 0, noiseLevel: 0.02 },
    'footsteps only': { breathLevel: 0, spm: 170, stepLevel: 0.8 },
    'wind only': { breathLevel: 0, spm: 0, windLevel: 0.08 },
    'digital silence': { breathLevel: 0, spm: 0, noiseLevel: 0 },
  };
  for (const [label, synth] of Object.entries(cases)) {
    const { estimates } = simulate({ synth });
    const valid = estimates.filter((e) => e.valid);
    assert.ok(valid.length <= 1, `${label}: ${valid.length} false readings, e.g. ${valid[0]?.rate}`);
  }
});

test('drops out quickly when breathing stops and recovers when it resumes', () => {
  const { estimates } = simulate({ seconds: 75, synth: { bpm: 34, spm: 170, stepLevel: 0.5, silences: [[30, 55]] } });
  const during = estimates.filter((e) => e.t >= 37 && e.t < 55);
  assert.equal(during.filter((e) => e.valid).length, 0, 'no readings while silent');
  const after = estimates.filter((e) => e.t >= 66);
  expectAccurate(score(after, 34, { fromSec: 66 }), 'after resuming');
});

test('tracks a gradual increase in effort', () => {
  const bpm = (t) => (t < 20 ? 28 : t < 80 ? 28 + (t - 20) * 0.3 : 46);
  const { estimates } = simulate({ seconds: 100, synth: { bpm, spm: 170, stepLevel: 0.6 } });
  // The estimator looks back ~10 s, so compare with the rate ~6 s earlier.
  const s = score(estimates, (t) => bpm(t - 6), { fromSec: 20, tolerance: () => 3 });
  expectAccurate(s, 'ramp', 0.85);
});

test('works at Bluetooth (16 kHz) and CD (44.1 kHz) sample rates', () => {
  for (const sampleRate of [16000, 44100]) {
    const { estimates } = simulate({ sampleRate, synth: { bpm: 35, spm: 170 } });
    expectAccurate(score(estimates, 35), `${sampleRate} Hz`);
  }
});

test('is not fooled by the microphone gain', () => {
  for (const level of [0.005, 0.2, 0.9]) {
    const { estimates } = simulate({ synth: { bpm: 33, breathLevel: level, stepLevel: level * 2, noiseLevel: level / 50 } });
    expectAccurate(score(estimates, 33), `breath level ${level}`);
  }
});

test('randomised robustness sweep', () => {
  let bad = 0, total = 0;
  for (let seed = 1; seed <= 8; seed++) {
    for (const bpm of [18, 30, 42, 56]) {
      const { estimates } = simulate({
        sampleRate: 32000,
        synth: {
          seed, bpm, spm: 150 + seed * 5, stepLevel: 0.3 + 0.12 * seed, noiseLevel: 0.002 * seed,
          windLevel: seed % 3 ? 0 : 0.03, inhaleLevel: (seed % 4) * 0.25,
        },
      });
      for (const e of estimates.filter((x) => x.t >= 18)) {
        total++;
        if (!e.valid || Math.abs(e.rate - bpm) > Math.max(2, bpm * 0.06)) bad++;
      }
    }
  }
  assert.ok(bad / total < 0.03, `${bad}/${total} estimates missing or off`);
});

test('cadence detector counts steps', () => {
  for (const spm of [150, 170, 190]) {
    const { cadence } = simulate({ withCadence: true, synth: { bpm: 36, spm, stepLevel: 0.6 } });
    const late = cadence.filter((c) => c.t >= 12);
    const good = late.filter((c) => c.valid && Math.abs(c.spm - spm) <= 3);
    assert.ok(good.length / late.length >= 0.9, `${spm} spm: ${good.length}/${late.length}`);
  }
  const { cadence } = simulate({ withCadence: true, synth: { bpm: 36, spm: 0 } });
  assert.ok(cadence.filter((c) => c.valid).length <= 1, 'no cadence without steps');
  for (const seed of [1, 2, 3]) {
    const noisy = simulate({ withCadence: true, synth: { seed, bpm: 30, spm: 0, noiseLevel: 0.03, windLevel: 0.05 } });
    assert.equal(noisy.cadence.filter((c) => c.valid).length, 0, `no cadence from wind and noise (seed ${seed})`);
  }
});

test('cadence survives footsteps that are quieter than the breathing', () => {
  // steps ~8 dB below the breath sounds, which also land on top of them
  const { cadence } = simulate({ seconds: 60, withCadence: true, synth: { bpm: 44, spm: 176, stepLevel: 0.1, breathLevel: 0.25 } });
  const late = cadence.filter((c) => c.t >= 12);
  const good = late.filter((c) => c.valid && Math.abs(c.spm - 176) <= 3);
  assert.ok(good.length / late.length >= 0.7, `${good.length}/${late.length}`);
});

test('synthesiser is deterministic for a seed', () => {
  const a = new BreathSynth(16000, { seed: 3 }).render(5000);
  const b = new BreathSynth(16000, { seed: 3 }).render(5000);
  const c = new BreathSynth(16000, { seed: 4 }).render(5000);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
});

test('activity (breathing animation) is a finite 0..1 value that follows the breaths', () => {
  const frames = [];
  const { detector } = simulate({ seconds: 25, synth: { bpm: 30, spm: 0 } });
  detector.onFrame = (f) => frames.push(f.activity);
  const s = new BreathSynth(48000, { bpm: 30, spm: 0, seed: 9 });
  for (let i = 0; i < 10 * 48000; i += 2048) detector.pushAudio(s.render(2048));
  assert.ok(frames.length > 200);
  assert.ok(frames.every((a) => Number.isFinite(a) && a >= 0 && a <= 1), 'finite and in range');
  const lo = Math.min(...frames), hi = Math.max(...frames);
  assert.ok(hi - lo > 0.5, `activity should swing with each breath (range ${lo.toFixed(2)}–${hi.toFixed(2)})`);
});
