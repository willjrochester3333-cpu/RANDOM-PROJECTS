import { h, fmtTime, fmtPct } from './dom.js';

/** Fill a <dl class="stats"> with the numbers for a finished run or analysis. */
export function renderRunStats(dl, run) {
  const secs = run.seconds || {};
  const tracked = (secs.in || 0) + (secs.above || 0) + (secs.below || 0);
  const share = (k) => (tracked > 0 ? (secs[k] || 0) / tracked : null);
  const count = (type) => (run.cues || []).filter((c) => c[1] === type).length;
  const items = [
    ['Time', fmtTime(run.durationSec)],
    ['Average', run.avgRate === null || run.avgRate === undefined ? '–' : `${Math.round(run.avgRate)}`],
    ['Peak', run.maxRate === null || run.maxRate === undefined ? '–' : `${Math.round(run.maxRate)}`],
    ['In zone', fmtPct(run.inZoneShare)],
    ['Above', fmtPct(share('above'))],
    ['Below', fmtPct(share('below'))],
    ['Slow-down cues', String(count('slow'))],
    ['Speed-up cues', String(count('speed'))],
  ];
  dl.replaceChildren(...items.map(([k, v]) => h('div', {}, h('dt', {}, k), h('dd', {}, v))));
}
