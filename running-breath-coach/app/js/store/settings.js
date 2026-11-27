// Persistent settings and run history (localStorage, guarded: private
// browsing modes can refuse storage and the app must still work).

const SETTINGS_KEY = 'breathpace.settings.v1';
const HISTORY_KEY = 'breathpace.history.v1';
const MAX_RUNS = 60;

export const ZONE_PRESETS = [
  { id: 'recovery', name: 'Recovery', low: 20, high: 26, hint: 'Very easy. Could breathe through your nose.' },
  { id: 'easy', name: 'Easy', low: 26, high: 34, hint: 'Conversational. Most of your running.' },
  { id: 'steady', name: 'Steady', low: 32, high: 40, hint: 'Comfortably hard. Short sentences.' },
  { id: 'tempo', name: 'Tempo', low: 38, high: 46, hint: 'Hard but controlled. A few words at a time.' },
  { id: 'intervals', name: 'Intervals', low: 44, high: 54, hint: 'Very hard repeats.' },
];

export const SETTINGS_DEFAULTS = {
  zonePreset: 'easy',
  zoneLow: 26,
  zoneHigh: 34,
  warmupMin: 2,
  dwellSec: 10,
  repeatSec: 45,
  inZoneCue: true,
  statusEveryMin: 0,
  voice: true,
  verbosity: 'detailed',
  voiceURI: '',
  speechRate: 1,
  tones: true,
  vibrate: true,
  breathMode: 'auto',
  micDeviceId: '',
  showCadence: true,
  keepAwake: true,
  demoSpeed: 3,
};

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function zoneName(s) {
  const p = ZONE_PRESETS.find((z) => z.id === s.zonePreset && z.low === s.zoneLow && z.high === s.zoneHigh);
  return p ? p.name : 'Custom';
}

export class SettingsStore extends EventTarget {
  constructor() {
    super();
    this.value = { ...SETTINGS_DEFAULTS, ...read(SETTINGS_KEY, {}) };
    this._sanitize();
  }

  _sanitize() {
    const v = this.value;
    const clamp = (x, lo, hi, d) => (Number.isFinite(+x) ? Math.min(hi, Math.max(lo, +x)) : d);
    v.zoneLow = Math.round(clamp(v.zoneLow, 8, 80, 26));
    v.zoneHigh = Math.round(clamp(v.zoneHigh, 10, 90, 34));
    if (v.zoneHigh - v.zoneLow < 2) v.zoneHigh = v.zoneLow + 2;
    v.warmupMin = clamp(v.warmupMin, 0, 15, 2);
    v.dwellSec = clamp(v.dwellSec, 4, 60, 10);
    v.repeatSec = clamp(v.repeatSec, 15, 300, 45);
    v.statusEveryMin = clamp(v.statusEveryMin, 0, 30, 0);
    v.speechRate = clamp(v.speechRate, 0.6, 1.6, 1);
    v.demoSpeed = clamp(v.demoSpeed, 1, 6, 3);
    if (!['auto', 'double'].includes(v.breathMode)) v.breathMode = 'auto';
    if (!['short', 'detailed'].includes(v.verbosity)) v.verbosity = 'detailed';
  }

  get() {
    return this.value;
  }

  set(patch) {
    Object.assign(this.value, patch);
    this._sanitize();
    write(SETTINGS_KEY, this.value);
    this.dispatchEvent(new CustomEvent('change', { detail: { patch, value: this.value } }));
  }

  reset() {
    this.value = { ...SETTINGS_DEFAULTS };
    write(SETTINGS_KEY, this.value);
    this.dispatchEvent(new CustomEvent('change', { detail: { patch: this.value, value: this.value } }));
  }
}

export const history = {
  list() {
    const runs = read(HISTORY_KEY, []);
    return Array.isArray(runs) ? runs : [];
  },
  add(run) {
    const runs = this.list().filter((r) => r.id !== run.id);
    runs.unshift(run);
    return write(HISTORY_KEY, runs.slice(0, MAX_RUNS));
  },
  remove(id) {
    write(HISTORY_KEY, this.list().filter((r) => r.id !== id));
  },
  clear() {
    write(HISTORY_KEY, []);
  },
};
