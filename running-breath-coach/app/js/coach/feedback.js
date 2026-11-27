// Delivers coach cues to the runner: spoken words, short tone patterns and
// vibration. Tones are distinct per direction so they work without speech:
// falling = slow down, rising = speed up, bright two-note = in the zone.

import { cueText, cueKind } from './phrases.js';

const TONES = {
  down: [[784, 0, 0.16], [523, 0.2, 0.3]],
  up: [[523, 0, 0.16], [784, 0.2, 0.3]],
  good: [[880, 0, 0.12], [1175, 0.13, 0.22]],
  warn: [[330, 0, 0.2], [330, 0.3, 0.2]],
  info: [[660, 0, 0.16]],
};

const VIBRATION = {
  down: [400, 150, 400],
  up: [120, 90, 120, 90, 120],
  good: [80],
  warn: [600],
  info: [60],
};

export class Feedback extends EventTarget {
  constructor(getSettings) {
    super();
    this.getSettings = getSettings;
    this.ctx = null;
    this.speechPrimed = false;
    this.voices = [];
    if ('speechSynthesis' in window) {
      const load = () => { this.voices = window.speechSynthesis.getVoices() || []; };
      load();
      window.speechSynthesis.addEventListener?.('voiceschanged', load);
    }
  }

  /** Call from inside a tap handler so mobile browsers allow sound later. */
  unlock() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        try { this.ctx = new AC(); } catch { this.ctx = null; }
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {});
    if (!this.speechPrimed && 'speechSynthesis' in window) {
      try {
        const u = new SpeechSynthesisUtterance(' ');
        u.volume = 0;
        window.speechSynthesis.speak(u);
      } catch { /* speech not available */ }
      this.speechPrimed = true;
    }
  }

  /** True when cues make sound the chest mic could pick up. */
  get audible() {
    const s = this.getSettings();
    return Boolean(s.voice || s.tones);
  }

  cue(cue) {
    const s = this.getSettings();
    const kind = cueKind(cue.type);
    const text = cueText(cue, s.verbosity);
    if (s.tones) this.tone(kind);
    if (s.vibrate) this.vibrate(kind);
    if (s.voice && text) {
      clearTimeout(this.sayTimer);
      this.sayTimer = setTimeout(() => this.say(text), s.tones ? 520 : 0);
    }
    this.dispatchEvent(new CustomEvent('cue', { detail: { cue, text, kind } }));
  }

  pickVoice() {
    const { voiceURI } = this.getSettings();
    const voices = this.voices.length ? this.voices : (window.speechSynthesis?.getVoices() || []);
    if (voiceURI) {
      const chosen = voices.find((v) => v.voiceURI === voiceURI);
      if (chosen) return chosen;
    }
    const english = voices.filter((v) => /^en(-|_|$)/i.test(v.lang));
    const lang = (navigator.language || 'en-US').toLowerCase();
    return english.find((v) => v.lang.toLowerCase() === lang) ||
      english.find((v) => v.default) || english.find((v) => v.localService) || english[0] || null;
  }

  say(text) {
    if (!('speechSynthesis' in window) || !text) return;
    const synth = window.speechSynthesis;
    try {
      // Newest information wins: drop anything still queued.
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      const voice = this.pickVoice();
      if (voice) { u.voice = voice; u.lang = voice.lang; } else { u.lang = 'en-US'; }
      u.rate = this.getSettings().speechRate || 1;
      u.volume = 1;
      synth.speak(u);
      // Chrome can leave the synthesiser paused after the tab was hidden.
      if (synth.paused) synth.resume();
    } catch { /* ignore speech failures; tones and captions still work */ }
  }

  tone(kind) {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    const t0 = ctx.currentTime + 0.02;
    for (const [freq, start, dur] of TONES[kind] || TONES.info) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0 + start);
      gain.gain.linearRampToValueAtTime(0.4, t0 + start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + start + dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t0 + start);
      osc.stop(t0 + start + dur + 0.05);
    }
  }

  vibrate(kind) {
    if (navigator.vibrate) {
      try { navigator.vibrate(VIBRATION[kind] || VIBRATION.info); } catch { /* unsupported */ }
    }
  }

  test() {
    this.unlock();
    const s = this.getSettings();
    this.cue({ type: 'slow', rate: s.zoneHigh + 6, zoneLow: s.zoneLow, zoneHigh: s.zoneHigh, strong: false });
  }
}
