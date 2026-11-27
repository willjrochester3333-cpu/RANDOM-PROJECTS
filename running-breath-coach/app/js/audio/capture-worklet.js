// AudioWorklet processor: collects microphone samples into 2048-sample
// chunks and hands them to the main thread, where all the analysis runs.

class BreathCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.size = opts.chunkSize || 2048;
    this.buf = new Float32Array(this.size);
    this.n = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (input && input.length) {
      const a = input[0];
      const b = input.length > 1 ? input[1] : null;
      for (let i = 0; i < a.length; i++) {
        this.buf[this.n++] = b ? 0.5 * (a[i] + b[i]) : a[i];
        if (this.n === this.size) {
          this.port.postMessage(this.buf, [this.buf.buffer]);
          this.buf = new Float32Array(this.size);
          this.n = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('breath-capture', BreathCaptureProcessor);
