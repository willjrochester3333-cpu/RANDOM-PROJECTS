import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Coach } from '../app/js/coach/coach.js';
import { cueText, cueKind } from '../app/js/coach/phrases.js';

/** Drive a coach with one estimate per second from a rate function. */
function drive(coach, seconds, rateAt, { validAt = () => true, start = 0 } = {}) {
  const log = [];
  for (let t = start; t <= start + seconds; t++) {
    const rate = rateAt(t);
    const res = coach.update({ t, rate, valid: rate !== null && validAt(t), confidence: 0.9 });
    for (const c of res.cues) log.push(c);
  }
  return log;
}

const types = (cues) => cues.map((c) => c.type);
const base = { zoneLow: 30, zoneHigh: 38, warmupSec: 0, dwellSec: 10, repeatSec: 45 };

test('locks on, then says slow down when breathing stays above the zone', () => {
  const coach = new Coach(base);
  const cues = drive(coach, 120, (t) => (t < 40 ? 34 : 46));
  assert.equal(cues[0].type, 'locked');
  const slow = cues.find((c) => c.type === 'slow');
  assert.ok(slow, 'expected a slow-down cue');
  // detector median needs a few seconds, plus 10 s of dwell
  assert.ok(slow.t >= 50 && slow.t <= 58, `slow cue at ${slow.t}`);
  assert.equal(slow.rate, 46);
  assert.equal(slow.strong, true, '46 is 8 above 38: strong');
  assert.equal(coach.state, 'above');
});

test('says speed up below the zone, but not during the warm-up', () => {
  const coach = new Coach({ ...base, warmupSec: 120 });
  const cues = drive(coach, 200, () => 24);
  const speed = cues.filter((c) => c.type === 'speed');
  assert.ok(speed.length >= 1);
  assert.ok(speed[0].t >= 120, `first speed-up at ${speed[0].t}, inside warm-up`);
  assert.ok(speed[0].t <= 121, 'owed cue is given as soon as warm-up ends');
});

test('slow down is still allowed during the warm-up', () => {
  const coach = new Coach({ ...base, warmupSec: 300 });
  const cues = drive(coach, 60, () => 50);
  assert.ok(types(cues).includes('slow'));
});

test('short excursions out of the zone are ignored', () => {
  const coach = new Coach(base);
  const cues = drive(coach, 120, (t) => (t >= 50 && t < 56 ? 44 : 34));
  assert.deepEqual(types(cues), ['locked']);
});

test('repeats reminders while out of zone, and confirms getting back in', () => {
  const coach = new Coach(base);
  const cues = drive(coach, 200, (t) => (t < 150 ? 44 : 34));
  const slow = cues.filter((c) => c.type === 'slow');
  assert.ok(slow.length >= 3, `expected repeats, got ${slow.length}`);
  for (let i = 1; i < slow.length; i++) assert.ok(slow[i].t - slow[i - 1].t >= 45);
  assert.ok(slow[1].repeat);
  const back = cues.find((c) => c.type === 'inzone');
  assert.ok(back && back.t > 150 && back.t < 165, `in-zone cue at ${back?.t}`);
});

test('holds off on nagging while the runner is already easing back', () => {
  const coach = new Coach(base);
  // above the zone, falling 1 bpm every 8 s towards it
  const cues = drive(coach, 160, (t) => (t < 20 ? 34 : Math.max(39.5, 50 - (t - 20) / 8)));
  const slow = cues.filter((c) => c.type === 'slow');
  const gaps = slow.slice(1).map((c, i) => c.t - slow[i].t);
  assert.ok(gaps.every((g) => g >= 45), `gaps ${gaps}`);
  assert.ok(slow.length <= 3, `${slow.length} cues while improving`);
});

test('hysteresis: hovering just over the edge does not flip-flop', () => {
  const coach = new Coach({ ...base, hysteresis: 1 });
  // 38.5 is above zoneHigh but within the 1 bpm hysteresis band
  const cues = drive(coach, 120, () => 38.5);
  assert.deepEqual(types(cues), ['locked']);
  assert.equal(coach.state, 'in');
});

test('reports a lost signal once, then the return of the signal', () => {
  const coach = new Coach({ ...base, lostSec: 20 });
  const cues = drive(coach, 160, (t) => (t >= 40 && t < 100 ? null : 34));
  assert.deepEqual(types(cues), ['locked', 'lost', 'back']);
  const lost = cues[1];
  assert.ok(lost.t >= 59 && lost.t <= 61, `lost at ${lost.t}`);
});

test('never hearing anything leads to a lost-signal cue', () => {
  const coach = new Coach({ ...base, lostSec: 20 });
  const cues = drive(coach, 30, () => null);
  assert.deepEqual(types(cues), ['lost']);
});

test('time-in-zone accounting', () => {
  const coach = new Coach(base);
  drive(coach, 300, (t) => (t < 150 ? 34 : 46));
  const s = coach.summary();
  assert.ok(s.inZoneShare > 0.4 && s.inZoneShare < 0.6, `in zone ${s.inZoneShare}`);
  assert.ok(s.seconds.above > 120);
});

test('recentMedian supports learning a zone from the current effort', () => {
  const coach = new Coach(base);
  drive(coach, 90, (t) => 31 + (t % 3));
  assert.equal(coach.recentMedian(60), 32);
});

test('periodic status cue', () => {
  const coach = new Coach({ ...base, statusEveryMin: 1 });
  const cues = drive(coach, 130, () => 34);
  const status = cues.filter((c) => c.type === 'status');
  assert.equal(status.length, 2);
  assert.equal(status[0].minutes, 1);
});

test('phrases', () => {
  const cue = { type: 'slow', rate: 46, zoneLow: 30, zoneHigh: 38, strong: false };
  assert.equal(cueText(cue), 'Slow down a little. Breathing 46, target 30 to 38.');
  assert.equal(cueText({ ...cue, strong: true }, 'short'), 'Ease right off.');
  assert.match(cueText({ ...cue, type: 'speed', rate: 24 }), /speed up/i);
  assert.equal(cueKind('slow'), 'down');
  assert.equal(cueKind('speed'), 'up');
  assert.equal(cueText({ type: 'status', minutes: 12, rate: 35, zoneLow: 30, zoneHigh: 38 }), '12 minutes. Breathing 35. In the zone.');
});
