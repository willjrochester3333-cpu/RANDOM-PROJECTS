import { BreathSynth } from '../app/js/sim/breath-synth.js';
import { BreathDetector } from '../app/js/dsp/breath-detector.js';
import { CadenceDetector } from '../app/js/dsp/cadence.js';

/**
 * Render synthetic chest-mic audio and run it through the detector in
 * 2048-sample chunks (the same chunk size the app's capture worklet uses).
 */
export function simulate({ seconds = 40, sampleRate = 48000, synth = {}, detector = {}, withCadence = false } = {}) {
  const s = new BreathSynth(sampleRate, synth);
  const det = new BreathDetector(sampleRate, detector);
  const estimates = [];
  const cadence = [];
  let cad = null;
  if (withCadence) {
    cad = new CadenceDetector(det.frontend.subRate);
    det.onFrontendFrame = (f) => cad.pushImpacts(f.impact);
  }
  det.onEstimate = (e) => {
    estimates.push(e);
    if (cad) cadence.push({ t: e.t, ...cad.estimate() });
  };
  const chunk = 2048;
  for (let done = 0; done < seconds * sampleRate; done += chunk) det.pushAudio(s.render(chunk));
  return { estimates, cadence, detector: det };
}

/** Summarise estimates after `fromSec`: share valid, and share within tolerance of truth. */
export function score(estimates, truth, { fromSec = 18, tolerance = (bpm) => Math.max(2, bpm * 0.06) } = {}) {
  const late = estimates.filter((e) => e.t >= fromSec);
  const truthAt = typeof truth === 'function' ? truth : () => truth;
  const valid = late.filter((e) => e.valid);
  const accurate = valid.filter((e) => Math.abs(e.rate - truthAt(e.t)) <= tolerance(truthAt(e.t)));
  return {
    count: late.length,
    validShare: late.length ? valid.length / late.length : 0,
    accurateShare: late.length ? accurate.length / late.length : 0,
    meanRate: valid.length ? valid.reduce((a, e) => a + e.rate, 0) / valid.length : null,
  };
}
