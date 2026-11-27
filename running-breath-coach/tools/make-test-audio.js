// Writes a synthetic "chest mic while running" WAV file for testing:
//   node tools/make-test-audio.js out.wav [seconds]
// Breathing sits at 30/min for 40 s, then climbs to 46/min (above the Easy
// zone), with footsteps, a little background noise and no real person.
import { writeFile } from 'node:fs/promises';
import { BreathSynth } from '../app/js/sim/breath-synth.js';
import { encodeWav } from '../app/js/audio/wav.js';

const out = process.argv[2] || 'breathing-test.wav';
const seconds = Number(process.argv[3] || 150);
const sampleRate = 48000;

export const scenarioBpm = (t) => (t < 40 ? 30 : t < 50 ? 30 + (t - 40) * 1.6 : 46);

const synth = new BreathSynth(sampleRate, {
  seed: 11,
  bpm: scenarioBpm,
  spm: (t) => (t < 40 ? 165 : 180),
  stepLevel: 0.25,
  breathLevel: 0.15,
  noiseLevel: 0.003,
});
const samples = synth.render(sampleRate * seconds);
await writeFile(out, Buffer.from(await encodeWav(samples, sampleRate).arrayBuffer()));
console.log(`wrote ${seconds} s of synthetic breathing to ${out}`);
