// Minimal 16-bit PCM WAV encoding plus a rolling buffer of recent audio, so
// a runner can save "the last 30 seconds" to check what the mic hears.

export function encodeWav(samples, sampleRate) {
  const n = samples.length;
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const str = (off, s) => { for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i)); };
  str(0, 'RIFF');
  v.setUint32(4, 36 + n * 2, true);
  str(8, 'WAVE');
  str(12, 'fmt ');
  v.setUint32(16, 16, true); // PCM chunk size
  v.setUint16(20, 1, true); // PCM
  v.setUint16(22, 1, true); // mono
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  str(36, 'data');
  v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: 'audio/wav' });
}

export class RecentAudio {
  constructor(sampleRate, seconds = 30) {
    this.sampleRate = sampleRate;
    this.data = new Int16Array(Math.round(sampleRate * seconds));
    this.pos = 0;
    this.filled = 0;
  }

  push(chunk) {
    const d = this.data;
    for (let i = 0; i < chunk.length; i++) {
      const s = Math.max(-1, Math.min(1, chunk[i]));
      d[this.pos] = s < 0 ? s * 0x8000 : s * 0x7fff;
      this.pos = (this.pos + 1) % d.length;
    }
    this.filled = Math.min(d.length, this.filled + chunk.length);
  }

  get seconds() {
    return this.filled / this.sampleRate;
  }

  toWav() {
    const n = this.filled;
    const out = new Float32Array(n);
    const start = (this.pos - n + this.data.length) % this.data.length;
    for (let i = 0; i < n; i++) out[i] = this.data[(start + i) % this.data.length] / 0x8000;
    return encodeWav(out, this.sampleRate);
  }
}
