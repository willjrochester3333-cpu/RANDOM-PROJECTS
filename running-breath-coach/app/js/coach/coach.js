// Coaching logic: turns a stream of breathing-rate estimates into
// "slow down" / "speed up" cues. Pure logic (no DOM), driven by the detector's
// audio clock so it behaves identically live, in the demo and in tests.

import { median } from '../dsp/periodicity.js';

export const COACH_DEFAULTS = {
  zoneLow: 26, // breaths per minute
  zoneHigh: 34,
  warmupSec: 120, // no "speed up" during the warm-up ("slow down" still allowed)
  dwellSec: 10, // how long the rate must stay out of zone before a cue
  repeatSec: 45, // reminder interval while it stays out of zone
  inZoneCue: true, // say so when you get back into the zone
  lostSec: 20, // no reliable reading for this long counts as signal lost
  lostRepeatSec: 180,
  smoothingSec: 8, // median over the valid estimates in this window
  hysteresis: 1, // bpm beyond a zone edge needed to leave the zone
  strongMargin: 0.15, // this far beyond the edge (as a fraction) is "way off"
  statusEveryMin: 0, // spoken status every N minutes (0 = off)
};

export const STATES = ['listening', 'in', 'above', 'below', 'lost'];

export class Coach {
  constructor(options = {}) {
    this.o = { ...COACH_DEFAULTS, ...options };
    this.reset();
  }

  reset() {
    this.state = 'listening';
    this.samples = []; // valid estimates within the smoothing window
    this.history = []; // valid estimates for the last 2 minutes (zone learning)
    this.smoothed = null;
    this.lastT = null;
    this.startT = null;
    this.lastValidT = null;
    this.everValid = false;
    this.pending = null;
    this.pendingSince = null;
    this.lastCue = { above: null, below: null, lost: null, any: null };
    this.lastCueRate = null;
    this.belowCueOwed = false;
    this.nextStatusT = null;
    this.time = { listening: 0, in: 0, above: 0, below: 0, lost: 0 };
  }

  setOptions(patch) {
    Object.assign(this.o, patch);
    if (this.o.zoneLow > this.o.zoneHigh) [this.o.zoneLow, this.o.zoneHigh] = [this.o.zoneHigh, this.o.zoneLow];
    // Re-judge against the new zone straight away, without the dwell delay
    // for getting back "in", so changing the zone mid-run feels responsive.
    this.pending = null;
    this.pendingSince = null;
  }

  /** Median of valid readings over the last `windowSec` seconds (null if too few). */
  recentMedian(windowSec = 60, minCount = 20) {
    if (this.lastT === null) return null;
    const from = this.lastT - windowSec;
    const vals = this.history.filter((s) => s.t >= from).map((s) => s.rate);
    return vals.length >= minCount ? median(vals) : null;
  }

  _classify(r) {
    const { zoneLow: lo, zoneHigh: hi, hysteresis: h } = this.o;
    if (this.state === 'above') return r > hi ? 'above' : r < lo - h ? 'below' : 'in';
    if (this.state === 'below') return r < lo ? 'below' : r > hi + h ? 'above' : 'in';
    return r > hi + h ? 'above' : r < lo - h ? 'below' : 'in';
  }

  _isStrong(r) {
    const { zoneLow: lo, zoneHigh: hi, strongMargin: m } = this.o;
    if (r > hi) return r - hi >= Math.max(4, hi * m);
    if (r < lo) return lo - r >= Math.max(4, lo * m);
    return false;
  }

  /**
   * Feed one detector estimate ({t, rate, valid, confidence}).
   * @returns {{state: string, rate: number|null, cues: object[]}}
   */
  update(est) {
    const t = est.t;
    const cues = [];
    if (this.startT === null) {
      this.startT = t;
      if (this.o.statusEveryMin > 0) this.nextStatusT = t + this.o.statusEveryMin * 60;
    }
    const dt = this.lastT === null ? 0 : Math.min(5, Math.max(0, t - this.lastT));
    this.lastT = t;
    this.time[this.state] += dt;

    if (est.valid && Number.isFinite(est.rate)) {
      this.samples.push({ t, rate: est.rate });
      this.history.push({ t, rate: est.rate });
      this.lastValidT = t;
      this.everValid = true;
    }
    const from = t - this.o.smoothingSec;
    while (this.samples.length && this.samples[0].t < from) this.samples.shift();
    while (this.history.length && this.history[0].t < t - 120) this.history.shift();

    const enough = this.samples.length >= 3 || (this.samples.length >= 1 && this.smoothed !== null);
    this.smoothed = enough ? median(this.samples.map((s) => s.rate)) : null;

    // What the readings say right now.
    let candidate;
    const quietFor = t - (this.lastValidT ?? this.startT);
    if (this.smoothed !== null) candidate = this._classify(this.smoothed);
    else if (quietFor >= this.o.lostSec) candidate = 'lost';
    else candidate = this.state; // brief dropout: keep the current verdict

    // Debounce: the new verdict has to hold for a while before it counts.
    if (candidate === this.state) {
      this.pending = null;
      this.pendingSince = null;
    } else {
      if (candidate !== this.pending) {
        this.pending = candidate;
        this.pendingSince = t;
      }
      const fromNoSignal = this.state === 'listening' || this.state === 'lost';
      const need = candidate === 'lost' ? 0 : candidate === 'in' || fromNoSignal ? this.o.dwellSec / 2 : this.o.dwellSec;
      if (t - this.pendingSince >= need) this._transition(candidate, t, cues);
    }

    // Reminders while still out of the zone.
    if ((this.state === 'above' || this.state === 'below') && this.smoothed !== null) {
      const last = this.lastCue[this.state];
      const warm = this.state === 'below' && t - this.startT < this.o.warmupSec;
      if (this.state === 'below' && this.belowCueOwed && !warm) {
        this._cue(cues, 'speed', t, { owed: true });
        this.belowCueOwed = false;
      } else if (last !== null && t - last >= this.o.repeatSec && !warm) {
        // If the runner is already heading back towards the zone, give them
        // a little longer before nagging again.
        const improving = this.lastCueRate !== null &&
          (this.state === 'above' ? this.smoothed <= this.lastCueRate - 2 : this.smoothed >= this.lastCueRate + 2);
        if (improving) {
          this.lastCue[this.state] = t - this.o.repeatSec / 2;
          this.lastCueRate = this.smoothed;
        } else {
          this._cue(cues, this.state === 'above' ? 'slow' : 'speed', t, { repeat: true });
        }
      }
    }

    // Optional periodic status.
    if (this.nextStatusT !== null && t >= this.nextStatusT) {
      this.nextStatusT += this.o.statusEveryMin * 60;
      if (this.lastCue.any === null || t - this.lastCue.any > 10) {
        this._cue(cues, 'status', t, { minutes: Math.round((t - this.startT) / 60) });
      }
    }

    return { state: this.state, rate: this.smoothed, cues };
  }

  _transition(to, t, cues) {
    const from = this.state;
    this.state = to;
    this.pending = null;
    this.pendingSince = null;
    if (to === 'above') {
      this._cue(cues, 'slow', t);
    } else if (to === 'below') {
      if (t - this.startT >= this.o.warmupSec) this._cue(cues, 'speed', t);
      else {
        this.belowCueOwed = true;
        this.lastCue.below = t;
      }
    } else if (to === 'in') {
      this.belowCueOwed = false;
      if (from === 'listening') this._cue(cues, 'locked', t);
      else if (from === 'lost') this._cue(cues, 'back', t);
      else if (this.o.inZoneCue) this._cue(cues, 'inzone', t);
    } else if (to === 'lost') {
      this.belowCueOwed = false;
      if (this.lastCue.lost === null || t - this.lastCue.lost >= this.o.lostRepeatSec) this._cue(cues, 'lost', t);
    }
  }

  _cue(cues, type, t, extra = {}) {
    const rate = this.smoothed;
    const cue = {
      type,
      t,
      rate: rate === null ? null : Math.round(rate),
      zoneLow: this.o.zoneLow,
      zoneHigh: this.o.zoneHigh,
      strong: rate !== null && (type === 'slow' || type === 'speed') && this._isStrong(rate),
      ...extra,
    };
    cues.push(cue);
    this.lastCue.any = t;
    if (type === 'slow') this.lastCue.above = t;
    if (type === 'speed') this.lastCue.below = t;
    if (type === 'lost') this.lastCue.lost = t;
    if (type === 'slow' || type === 'speed') this.lastCueRate = rate;
  }

  /** Session totals for the summary screen. */
  summary() {
    const tracked = this.time.in + this.time.above + this.time.below;
    return {
      seconds: { ...this.time },
      inZoneShare: tracked > 0 ? this.time.in / tracked : null,
    };
  }
}
