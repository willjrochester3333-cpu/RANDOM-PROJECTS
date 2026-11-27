export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** Tiny element builder: h('div', {class: 'x'}, 'text', child). Text is never parsed as HTML. */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v === null || v === undefined) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function fmtTime(sec) {
  if (!Number.isFinite(sec) || sec < 0) sec = 0;
  const s = Math.floor(sec % 60);
  const m = Math.floor(sec / 60) % 60;
  const hrs = Math.floor(sec / 3600);
  const ss = String(s).padStart(2, '0');
  return hrs ? `${hrs}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

export function fmtPct(share) {
  return share === null || share === undefined || !Number.isFinite(share) ? '–' : `${Math.round(share * 100)}%`;
}

let toastTimer = null;
export function toast(message, ms = 4000) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

/**
 * Press-and-hold button: fills over `ms`, fires `onDone` when full. Stops
 * pocket bumps and sweaty taps from ending a run.
 */
export function holdButton(btn, ms, onDone) {
  let start = null;
  let raf = 0;
  const reset = () => {
    start = null;
    cancelAnimationFrame(raf);
    btn.style.setProperty('--p', '0');
  };
  const frame = (now) => {
    if (start === null) return;
    const p = Math.min(1, (now - start) / ms);
    btn.style.setProperty('--p', String(p));
    if (p >= 1) {
      reset();
      onDone();
    } else {
      raf = requestAnimationFrame(frame);
    }
  };
  const begin = (e) => {
    if (start !== null) return;
    if (e && e.type === 'pointerdown') btn.setPointerCapture?.(e.pointerId);
    start = performance.now();
    raf = requestAnimationFrame(frame);
  };
  btn.addEventListener('pointerdown', begin);
  btn.addEventListener('pointerup', reset);
  btn.addEventListener('pointercancel', reset);
  btn.addEventListener('lostpointercapture', reset);
  btn.addEventListener('contextmenu', (e) => e.preventDefault());
  btn.addEventListener('keydown', (e) => {
    if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); begin(); }
  });
  btn.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') reset(); });
  btn.addEventListener('click', (e) => e.preventDefault());
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = h('a', { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
