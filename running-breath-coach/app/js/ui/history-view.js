import { $, h, fmtTime } from './dom.js';
import { drawRateChart } from './charts.js';
import { renderRunStats } from './run-stats.js';
import { history } from '../store/settings.js';

const dateFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export function initHistoryView({ engine }) {
  const el = {
    list: $('#run-list'), empty: $('#history-empty'), detail: $('#run-detail'), title: $('#detail-title'),
    chart: $('#detail-chart'), stats: $('#detail-stats'), close: $('#btn-detail-close'),
    del: $('#btn-detail-delete'), confirm: $('#detail-confirm'), yes: $('#btn-detail-delete-yes'), no: $('#btn-detail-delete-no'),
  };
  let current = null;

  function renderList() {
    const runs = history.list();
    el.empty.hidden = runs.length > 0;
    el.list.replaceChildren(...runs.map((run) => {
      const share = run.inZoneShare === null || run.inZoneShare === undefined ? '–' : `${Math.round(run.inZoneShare * 100)}%`;
      return h('li', {}, h('button', { class: 'run-item', type: 'button', onclick: () => openRun(run) },
        h('span', { class: 'when' }, dateFmt.format(new Date(run.startedAt))),
        h('span', { class: 'share' }, share, h('small', {}, 'in zone')),
        h('span', { class: 'meta' }, `${fmtTime(run.durationSec)} · avg ${run.avgRate === null ? '–' : Math.round(run.avgRate)} · zone ${run.zone.low}–${run.zone.high}`),
      ));
    }));
  }

  function openRun(run) {
    current = run;
    el.title.textContent = dateFmt.format(new Date(run.startedAt));
    renderRunStats(el.stats, run);
    el.detail.hidden = false;
    el.confirm.hidden = true;
    el.del.hidden = false;
    requestAnimationFrame(() => {
      drawRateChart(el.chart, { series: run.series, zone: run.zone, cues: run.cues });
      el.detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  el.close.addEventListener('click', () => { el.detail.hidden = true; current = null; });
  el.del.addEventListener('click', () => { el.confirm.hidden = false; el.del.hidden = true; });
  el.no.addEventListener('click', () => { el.confirm.hidden = true; el.del.hidden = false; });
  el.yes.addEventListener('click', () => {
    if (current) history.remove(current.id);
    el.detail.hidden = true;
    current = null;
    renderList();
  });
  engine.addEventListener('stopped', renderList);

  renderList();
  return {
    onShow() {
      renderList();
      if (current) drawRateChart(el.chart, { series: current.series, zone: current.zone, cues: current.cues });
    },
  };
}
