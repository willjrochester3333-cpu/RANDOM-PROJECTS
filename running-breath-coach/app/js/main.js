import { $, $$ } from './ui/dom.js';
import { SettingsStore } from './store/settings.js';
import { Feedback } from './coach/feedback.js';
import { RunEngine } from './engine.js';
import { initRunView } from './ui/run-view.js';
import { initCheckView } from './ui/check-view.js';
import { initHistoryView } from './ui/history-view.js';
import { initSetupView } from './ui/setup-view.js';

const settings = new SettingsStore();
const feedback = new Feedback(() => settings.get());
const engine = new RunEngine({ settings, feedback });

const VIEWS = ['run', 'check', 'history', 'setup'];
let currentView = 'run';

const run = initRunView({ engine, settings });
const check = initCheckView({ engine, settings, isVisible: () => currentView === 'check' });
const hist = initHistoryView({ engine });
const setup = initSetupView({ settings, feedback });
const hooks = { run: { onShow: run.redraw }, check, history: hist, setup };

function route() {
  const name = location.hash.replace('#', '');
  const view = VIEWS.includes(name) ? name : 'run';
  const changed = view !== currentView;
  currentView = view;
  for (const v of VIEWS) $(`#view-${v}`).hidden = v !== view;
  for (const a of $$('.tabbar a')) {
    if (a.dataset.view === view) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  if (changed) window.scrollTo({ top: 0 });
  hooks[view]?.onShow?.();
}
window.addEventListener('hashchange', route);
route();

$('#zone-chip').addEventListener('click', () => {
  location.hash = '#setup';
  requestAnimationFrame(() => $('#zone-section').scrollIntoView({ block: 'start' }));
});

engine.addEventListener('status', (e) => {
  if (e.detail.status === 'running' && engine.kind === 'live') window.dispatchEvent(new Event('breathpace:mic-allowed'));
});

// Ask before closing the page mid-run (a stray swipe shouldn't lose a run).
window.addEventListener('beforeunload', (e) => {
  if (engine.running && engine.kind === 'live') {
    e.preventDefault();
    e.returnValue = '';
  }
});

if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* offline support is optional */ });
}

// Handy for debugging from the console (and used by the end-to-end test).
window.breathpace = { engine, settings, feedback };
