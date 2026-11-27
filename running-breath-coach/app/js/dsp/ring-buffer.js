/** Fixed-capacity ring buffer of numbers (float64) with ordered read-out. */
export class RingBuffer {
  constructor(capacity) {
    this.capacity = capacity;
    this.data = new Float64Array(capacity);
    this.pos = 0; // next write index
    this.length = 0;
  }

  push(v) {
    this.data[this.pos] = v;
    this.pos = (this.pos + 1) % this.capacity;
    if (this.length < this.capacity) this.length++;
  }

  /** Value `back` samples before the newest one (0 = newest). */
  get(back = 0) {
    return this.data[(this.pos - 1 - back + this.capacity * 2) % this.capacity];
  }

  /** Copy the newest `n` values, oldest first, into `out`. */
  latest(n = this.length, out = new Float64Array(n)) {
    n = Math.min(n, this.length);
    const start = (this.pos - n + this.capacity) % this.capacity;
    const first = Math.min(n, this.capacity - start);
    out.set(this.data.subarray(start, start + first), 0);
    if (first < n) out.set(this.data.subarray(0, n - first), first);
    return n === out.length ? out : out.subarray(0, n);
  }

  clear() {
    this.pos = 0;
    this.length = 0;
  }
}
