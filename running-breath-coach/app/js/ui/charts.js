// Canvas charts. Colours come from the CSS tokens so both themes work.

const STATE_TOKEN = ['--lost', '--in', '--above', '--below', '--lost'];

function tokens() {
  const cs = getComputedStyle(document.documentElement);
  const get = (n) => cs.getPropertyValue(n).trim();
  return {
    text: get('--text'), muted: get('--muted'), line: get('--line'), surface2: get('--surface-2'),
    in: get('--in'), above: get('--above'), below: get('--below'), lost: get('--lost'), accent: get('--accent'),
    font: get('--font-body') || 'system-ui',
    state: STATE_TOKEN.map(get),
  };
}

/** Size the canvas backing store to its CSS box and return a 2D context in CSS pixels. */
function setup(canvas) {
  const dpr = Math.min(3, window.devicePixelRatio || 1);
  const w = Math.max(10, Math.round(canvas.clientWidth || canvas.parentElement?.clientWidth || 300));
  const hAttr = Number(canvas.getAttribute('height')) || 120;
  const hCss = canvas.dataset.h ? Number(canvas.dataset.h) : hAttr;
  if (!canvas.dataset.h) canvas.dataset.h = String(hAttr);
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(hCss * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(hCss * dpr);
    canvas.style.height = `${hCss}px`;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, hCss);
  return { ctx, w, h: hCss };
}

function alpha(color, a) {
  // tokens are hex (#rrggbb); fall back to the colour itself otherwise
  const m = /^#([0-9a-f]{6})$/i.exec(color);
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

const niceStep = (span) => (span > 60 ? 20 : span > 30 ? 10 : 5);

/**
 * Breathing rate over time.
 * @param {HTMLCanvasElement} canvas
 * @param {{series: Array<[number, number|null, number]>, zone: {low:number, high:number}, cues?: Array<[number,string,number]>, windowSec?: number, now?: number}} data
 */
export function drawRateChart(canvas, { series, zone, cues = [], windowSec = 0, now = null }) {
  const { ctx, w, h } = setup(canvas);
  const t = tokens();
  const left = 30, right = 8, top = 12, bottom = 20;
  const pw = w - left - right, ph = h - top - bottom;

  const tEnd = Math.max(60, now ?? (series.length ? series[series.length - 1][0] : 0));
  const tStart = windowSec ? Math.max(0, tEnd - windowSec) : 0;
  const vis = series.filter((p) => p[0] >= tStart);
  const rates = vis.map((p) => p[1]).filter((v) => v !== null);
  let yMin = Math.min(zone.low - 6, ...(rates.length ? [Math.min(...rates) - 3] : []));
  let yMax = Math.max(zone.high + 6, ...(rates.length ? [Math.max(...rates) + 3] : []));
  yMin = Math.max(0, Math.floor(yMin / 5) * 5);
  yMax = Math.ceil(yMax / 5) * 5;
  const X = (s) => left + ((s - tStart) / Math.max(1, tEnd - tStart)) * pw;
  const Y = (v) => top + (1 - (v - yMin) / Math.max(1, yMax - yMin)) * ph;

  ctx.font = `12px ${t.font}`;
  ctx.textBaseline = 'middle';
  // grid + y labels
  const step = niceStep(yMax - yMin);
  ctx.strokeStyle = t.line;
  ctx.fillStyle = t.muted;
  ctx.lineWidth = 1;
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) {
    ctx.beginPath();
    ctx.moveTo(left, Math.round(Y(v)) + 0.5);
    ctx.lineTo(w - right, Math.round(Y(v)) + 0.5);
    ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(String(v), left - 6, Y(v));
  }
  // zone band
  ctx.fillStyle = alpha(t.in, 0.16);
  ctx.fillRect(left, Y(zone.high), pw, Y(zone.low) - Y(zone.high));
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = alpha(t.in, 0.8);
  for (const v of [zone.low, zone.high]) {
    ctx.beginPath();
    ctx.moveTo(left, Y(v));
    ctx.lineTo(w - right, Y(v));
    ctx.stroke();
  }
  ctx.setLineDash([]);
  // x labels in minutes
  const spanMin = (tEnd - tStart) / 60;
  const xStep = spanMin > 40 ? 10 : spanMin > 16 ? 5 : spanMin > 6 ? 2 : 1;
  ctx.fillStyle = t.muted;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  for (let m = Math.ceil(tStart / 60 / xStep) * xStep; m * 60 <= tEnd; m += xStep) {
    const x = X(m * 60);
    if (x < left + 8 || x > w - right - 8) continue;
    ctx.fillText(`${m}m`, x, h - 4);
  }
  // rate line, coloured by zone state
  ctx.lineWidth = 2.5;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  for (let i = 1; i < vis.length; i++) {
    const a = vis[i - 1], b = vis[i];
    if (a[1] === null || b[1] === null || b[0] - a[0] > 15) continue;
    ctx.strokeStyle = t.state[b[2]] || t.text;
    ctx.beginPath();
    ctx.moveTo(X(a[0]), Y(a[1]));
    ctx.lineTo(X(b[0]), Y(b[1]));
    ctx.stroke();
  }
  // emphasise the newest point
  const last = [...vis].reverse().find((p) => p[1] !== null);
  if (last) {
    ctx.fillStyle = t.state[last[2]] || t.text;
    ctx.beginPath();
    ctx.arc(X(last[0]), Y(last[1]), 4, 0, Math.PI * 2);
    ctx.fill();
  }
  // cue markers along the top: ▼ slow down, ▲ speed up
  for (const [ct, type] of cues) {
    if (ct < tStart || (type !== 'slow' && type !== 'speed')) continue;
    const x = X(ct);
    ctx.fillStyle = type === 'slow' ? t.above : t.below;
    ctx.beginPath();
    if (type === 'slow') { ctx.moveTo(x - 5, top - 9); ctx.lineTo(x + 5, top - 9); ctx.lineTo(x, top - 1); }
    else { ctx.moveTo(x - 5, top - 1); ctx.lineTo(x + 5, top - 1); ctx.lineTo(x, top - 9); }
    ctx.closePath();
    ctx.fill();
  }
}

/** Scrolling breath-sound trace (values 0..1, oldest first). */
export function drawScope(canvas, values, color) {
  const { ctx, w, h } = setup(canvas);
  const t = tokens();
  ctx.strokeStyle = t.line;
  ctx.beginPath();
  ctx.moveTo(0, h - 0.5);
  ctx.lineTo(w, h - 0.5);
  ctx.stroke();
  if (values.length < 2) return;
  const n = values.length;
  ctx.beginPath();
  ctx.moveTo(0, h);
  for (let i = 0; i < n; i++) ctx.lineTo((i / (n - 1)) * w, h - 4 - values[i] * (h - 10));
  ctx.lineTo(w, h);
  ctx.closePath();
  ctx.fillStyle = alpha(color || t.accent, 0.22);
  ctx.fill();
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = (i / (n - 1)) * w, y = h - 4 - values[i] * (h - 10);
    if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
  }
  ctx.strokeStyle = color || t.accent;
  ctx.lineWidth = 2;
  ctx.stroke();
}

/** Rhythm strength (summary correlation) against breathing rate. */
export function drawCurve(canvas, curve, envRate, { minBpm = 10, maxBpm = 75, chosenBpm = null } = {}) {
  const { ctx, w, h } = setup(canvas);
  const t = tokens();
  const left = 8, right = 8, top = 8, bottom = 18;
  const pw = w - left - right, ph = h - top - bottom;
  const X = (bpm) => left + ((bpm - minBpm) / (maxBpm - minBpm)) * pw;
  const Y = (v) => top + (1 - Math.max(0, Math.min(1, v))) * ph;
  ctx.font = `12px ${t.font}`;
  ctx.fillStyle = t.muted;
  ctx.textAlign = 'center';
  ctx.strokeStyle = t.line;
  for (let b = 10; b <= maxBpm; b += 10) {
    const x = X(b);
    ctx.beginPath();
    ctx.moveTo(x + 0.5, top);
    ctx.lineTo(x + 0.5, top + ph);
    ctx.stroke();
    ctx.fillText(String(b), x, h - 3);
  }
  if (!curve) return;
  ctx.beginPath();
  let started = false;
  for (let lag = curve.length - 1; lag >= 1; lag--) {
    const bpm = (60 * envRate) / lag;
    if (bpm < minBpm || bpm > maxBpm) continue;
    const x = X(bpm), y = Y(curve[lag]);
    if (started) ctx.lineTo(x, y); else { ctx.moveTo(x, y); started = true; }
  }
  ctx.strokeStyle = t.accent;
  ctx.lineWidth = 2;
  ctx.stroke();
  if (chosenBpm) {
    const x = X(chosenBpm);
    ctx.strokeStyle = t.in;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, top + ph);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = t.text;
    ctx.textAlign = x > w - 60 ? 'right' : 'left';
    ctx.fillText(`${Math.round(chosenBpm)}/min`, x + (x > w - 60 ? -6 : 6), top + 10);
  }
}
