// Offline analysis of a recording: the same detector and coach as a live run,
// fed as fast as possible. No DOM; also runs under Node for tests.

import { BreathDetector } from './dsp/breath-detector.js';
import { CadenceDetector } from './dsp/cadence.js';
import { Coach } from './coach/coach.js';

const STATE_CODES = { listening: 0, in: 1, above: 2, below: 3, lost: 4 };

export async function analyzeSamples(samples, sampleRate, coachOpts, { mode = 'auto', onProgress = null } = {}) {
  const det = new BreathDetector(sampleRate, { mode });
  const cad = new CadenceDetector(det.frontend.subRate);
  det.onFrontendFrame = (f) => cad.pushImpacts(f.impact);
  const coach = new Coach(coachOpts);
  const series = [];
  const cues = [];
  const cadence = [];
  det.onEstimate = (est) => {
    const res = coach.update(est);
    for (const c of res.cues) cues.push([Math.round(c.t), c.type, c.rate, c]);
    series.push([Math.round(est.t * 10) / 10, res.rate === null ? null : Math.round(res.rate * 10) / 10, STATE_CODES[res.state]]);
    const c = cad.estimate();
    if (c.valid) cadence.push([Math.round(est.t), Math.round(c.spm)]);
  };
  const chunk = 4096;
  const yieldEvery = sampleRate * 15; // keep the page responsive
  let sinceYield = 0;
  for (let i = 0; i < samples.length; i += chunk) {
    det.pushAudio(samples.subarray(i, Math.min(i + chunk, samples.length)));
    sinceYield += chunk;
    if (sinceYield >= yieldEvery) {
      sinceYield = 0;
      if (onProgress) onProgress(i / samples.length);
      await new Promise((r) => setTimeout(r, 0));
    }
  }
  if (onProgress) onProgress(1);
  const rates = series.map((p) => p[1]).filter((v) => v !== null);
  const sum = coach.summary();
  return {
    durationSec: samples.length / sampleRate,
    series,
    cues,
    cadence,
    avgRate: rates.length ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
    maxRate: rates.length ? Math.max(...rates) : null,
    inZoneShare: sum.inZoneShare,
    seconds: sum.seconds,
    coveredShare: series.length ? rates.length / series.length : 0,
  };
}
