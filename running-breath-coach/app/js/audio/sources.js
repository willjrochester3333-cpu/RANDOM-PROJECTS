// Audio sources. Each one calls `onAudio(Float32Array)` with mono chunks and
// exposes `sampleRate`, `start()`, `stop()` and an optional `onEnded`.

import { BreathSynth } from '../sim/breath-synth.js';

const CHUNK = 2048;

export class MicError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

/** Explain a getUserMedia failure in words a runner can act on. */
function micError(err) {
  const name = err && err.name;
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return new MicError('denied', 'Microphone access was blocked. Allow the microphone for this site in your browser settings, then try again.');
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return new MicError('notfound', 'No microphone was found. Plug in your clip-on mic (or pick another one in Setup) and try again.');
  }
  if (name === 'NotReadableError') {
    return new MicError('busy', 'The microphone is busy in another app. Close the other app and try again.');
  }
  return new MicError('other', `Could not start the microphone (${(err && err.message) || err}).`);
}

export class MicSource {
  constructor({ deviceId = '' } = {}) {
    this.kind = 'live';
    this.deviceId = deviceId;
    this.onAudio = null;
    this.onEnded = null;
    this.ctx = null;
    this.stream = null;
    this.label = 'Microphone';
    this.sampleRate = 48000;
    this.usingWorklet = false;
  }

  /**
   * Must be called from a tap/click handler: the AudioContext is created
   * before the first await so mobile browsers allow it to start.
   */
  async open() {
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new MicError('insecure', 'This page needs to be opened over https:// (or localhost) to use the microphone.');
    }
    const AC = window.AudioContext || window.webkitAudioContext;
    this.ctx = new AC({ latencyHint: 'playback' });
    const resumed = this.ctx.resume().catch(() => {});
    const audio = {
      // Breath sounds are noise-like: noise suppression, echo cancellation
      // and automatic gain would all distort or remove them.
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
      channelCount: { ideal: 1 },
    };
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: this.deviceId ? { ...audio, deviceId: { exact: this.deviceId } } : audio,
        video: false,
      });
    } catch (err) {
      if (this.deviceId && (err.name === 'OverconstrainedError' || err.name === 'NotFoundError')) {
        // The saved mic isn't plugged in: fall back to the default input.
        try {
          this.stream = await navigator.mediaDevices.getUserMedia({ audio, video: false });
        } catch (err2) {
          this.close();
          throw micError(err2);
        }
      } else {
        this.close();
        throw micError(err);
      }
    }
    await resumed;
    const track = this.stream.getAudioTracks()[0];
    this.label = (track && track.label) || 'Microphone';
    if (track) track.addEventListener('ended', () => this.onEnded && this.onEnded());
    this.sampleRate = this.ctx.sampleRate;

    const src = this.ctx.createMediaStreamSource(this.stream);
    let node;
    try {
      const url = new URL('./capture-worklet.js', import.meta.url);
      await this.ctx.audioWorklet.addModule(url);
      node = new AudioWorkletNode(this.ctx, 'breath-capture', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
        processorOptions: { chunkSize: CHUNK },
      });
      node.port.onmessage = (e) => { if (this.running && this.onAudio) this.onAudio(e.data); };
      this.usingWorklet = true;
    } catch {
      // Older browsers: ScriptProcessorNode is deprecated but still works.
      node = this.ctx.createScriptProcessor(CHUNK, 1, 1);
      node.onaudioprocess = (e) => {
        if (this.running && this.onAudio) this.onAudio(new Float32Array(e.inputBuffer.getChannelData(0)));
      };
    }
    // Route through a muted gain so the graph is pulled without being heard.
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    src.connect(node);
    node.connect(mute);
    mute.connect(this.ctx.destination);
    this.node = node;
    return this;
  }

  start() {
    this.running = true;
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {});
  }

  stop() {
    this.running = false;
    this.close();
  }

  close() {
    if (this.stream) for (const t of this.stream.getTracks()) t.stop();
    this.stream = null;
    if (this.node) {
      try { this.node.disconnect(); } catch { /* already gone */ }
      if (this.node.port) this.node.port.onmessage = null;
    }
    if (this.ctx && this.ctx.state !== 'closed') this.ctx.close().catch(() => {});
    this.ctx = null;
  }
}

/** Breathing-rate script for the demo, relative to the target zone. */
export function demoScenario(lo, hi) {
  const mid = (lo + hi) / 2;
  const pts = [
    [0, lo - 5], [50, mid], [110, mid], [140, hi + 7], [200, hi + 7], [230, mid],
    [280, mid], [310, lo - 6], [370, lo - 6], [400, mid], [450, mid],
  ];
  const loop = pts[pts.length - 1][0];
  return (t) => {
    const u = t % loop;
    for (let i = 1; i < pts.length; i++) {
      const [t1, v1] = pts[i];
      const [t0, v0] = pts[i - 1];
      if (u <= t1) return v0 + ((v1 - v0) * (u - t0)) / (t1 - t0);
    }
    return mid;
  };
}

/** Synthetic breathing in (sped-up) real time, for trying the app without a mic. */
export class DemoSource {
  constructor({ zoneLow = 26, zoneHigh = 34, speed = 3, sampleRate = 16000, seed = Date.now() % 100000 } = {}) {
    this.kind = 'demo';
    this.label = `Demo (${speed}× speed)`;
    this.sampleRate = sampleRate;
    this.speed = speed;
    const bpm = demoScenario(zoneLow, zoneHigh);
    this.synth = new BreathSynth(sampleRate, {
      seed,
      bpm,
      spm: (t) => Math.max(150, Math.min(192, 150 + (bpm(t) - 20) * 1.1)),
      stepLevel: 0.2,
      inhaleLevel: 0.4,
      noiseLevel: 0.002,
      breathLevel: (t) => 0.05 + 0.002 * bpm(t),
    });
    this.onAudio = null;
    this.timer = null;
  }

  async open() { return this; }

  start() {
    this.t0 = performance.now();
    this.done = 0;
    const tick = () => {
      const due = Math.floor(((performance.now() - this.t0) / 1000) * this.sampleRate * this.speed);
      // Catch up after the tab was throttled, but never more than 3 s at once.
      let budget = Math.ceil((this.sampleRate * 3) / CHUNK);
      while (this.done + CHUNK <= due && budget-- > 0) {
        const chunk = this.synth.render(CHUNK);
        this.done += CHUNK;
        if (this.onAudio) this.onAudio(chunk);
      }
      if (this.done + CHUNK * 4 < due) this.t0 += ((due - this.done) / this.sampleRate / this.speed) * 1000;
    };
    this.timer = setInterval(tick, 40);
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
  }
}

/** Decode an audio file into mono samples at a modest sample rate. */
export async function decodeRecording(file) {
  const data = await file.arrayBuffer();
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  let lastErr;
  for (const rate of [16000, 22050, 44100]) {
    try {
      const ctx = new OAC(1, 1, rate);
      const buf = await ctx.decodeAudioData(data.slice(0));
      const n = buf.length;
      const mono = new Float32Array(n);
      for (let c = 0; c < buf.numberOfChannels; c++) {
        const ch = buf.getChannelData(c);
        for (let i = 0; i < n; i++) mono[i] += ch[i] / buf.numberOfChannels;
      }
      return { samples: mono, sampleRate: buf.sampleRate, duration: buf.duration };
    } catch (err) {
      lastErr = err;
    }
  }
  throw new Error(`This file could not be decoded as audio (${(lastErr && lastErr.message) || lastErr}). Try a WAV, M4A or MP3 file.`);
}
