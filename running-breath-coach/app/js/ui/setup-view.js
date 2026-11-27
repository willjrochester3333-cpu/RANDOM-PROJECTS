import { $, $$, h, toast } from './dom.js';
import { ZONE_PRESETS } from '../store/settings.js';

const NUMERIC = new Set(['zoneLow', 'zoneHigh', 'warmupMin', 'dwellSec', 'repeatSec', 'statusEveryMin', 'speechRate', 'demoSpeed']);

export function initSetupView({ settings, feedback }) {
  const form = $('#settings-form');
  const presets = $('#zone-presets');

  presets.replaceChildren(...ZONE_PRESETS.map((p) => h('button', {
    type: 'button',
    class: 'preset',
    role: 'radio',
    'data-preset': p.id,
    onclick: () => settings.set({ zonePreset: p.id, zoneLow: p.low, zoneHigh: p.high }),
  }, h('b', {}, p.name), h('span', { class: 'range' }, `${p.low}–${p.high}`), h('span', {}, p.hint))));

  function fill() {
    const s = settings.get();
    for (const input of $$('[id^="set-"]', form)) {
      const key = input.id.slice(4);
      if (!(key in s)) continue;
      if (input.type === 'checkbox') input.checked = Boolean(s[key]);
      else if (document.activeElement !== input) input.value = String(s[key]);
    }
    for (const b of $$('.preset', presets)) {
      const p = ZONE_PRESETS.find((z) => z.id === b.dataset.preset);
      const on = p && s.zoneLow === p.low && s.zoneHigh === p.high;
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    }
  }

  form.addEventListener('change', (e) => {
    const input = e.target;
    if (!input.id || !input.id.startsWith('set-')) return;
    const key = input.id.slice(4);
    let value = input.type === 'checkbox' ? input.checked : input.value;
    if (NUMERIC.has(key)) value = Number(value);
    const patch = { [key]: value };
    if (key === 'zoneLow' || key === 'zoneHigh') patch.zonePreset = 'custom';
    settings.set(patch);
  });
  form.addEventListener('submit', (e) => e.preventDefault());

  form.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-step]');
    if (!btn) return;
    const [key, delta] = btn.dataset.step.split(':');
    const s = settings.get();
    settings.set({ [key]: s[key] + Number(delta), zonePreset: 'custom' });
  });

  // Voices arrive asynchronously in most browsers.
  const voiceSelect = $('#set-voiceURI');
  function fillVoices() {
    if (!('speechSynthesis' in window)) return;
    const voices = window.speechSynthesis.getVoices() || [];
    const en = voices.filter((v) => /^en/i.test(v.lang));
    const rest = voices.filter((v) => !/^en/i.test(v.lang));
    voiceSelect.replaceChildren(h('option', { value: '' }, 'Automatic'),
      ...[...en, ...rest].map((v) => h('option', { value: v.voiceURI }, `${v.name} (${v.lang})`)));
    voiceSelect.value = settings.get().voiceURI;
  }
  if ('speechSynthesis' in window) {
    fillVoices();
    window.speechSynthesis.addEventListener?.('voiceschanged', fillVoices);
  } else {
    voiceSelect.disabled = true;
  }

  // Microphones: names only appear once permission has been granted.
  const micSelect = $('#set-micDeviceId');
  async function fillMics() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    try {
      const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audioinput');
      const named = devices.some((d) => d.label);
      $('#mic-names-note').hidden = named;
      micSelect.replaceChildren(h('option', { value: '' }, 'Default microphone'),
        ...devices.filter((d) => d.deviceId && d.deviceId !== 'default')
          .map((d, i) => h('option', { value: d.deviceId }, d.label || `Microphone ${i + 1}`)));
      micSelect.value = settings.get().micDeviceId;
      if (micSelect.value !== settings.get().micDeviceId) micSelect.value = '';
    } catch { /* not available */ }
  }
  navigator.mediaDevices?.addEventListener?.('devicechange', fillMics);
  window.addEventListener('breathpace:mic-allowed', fillMics);
  fillMics();

  $('#btn-test-voice').addEventListener('click', () => {
    feedback.test();
    if (!settings.get().voice && !settings.get().tones) toast('Spoken cues and tones are both off.');
  });

  const resetConfirm = $('#reset-confirm');
  $('#btn-reset').addEventListener('click', () => { resetConfirm.hidden = false; });
  $('#btn-reset-no').addEventListener('click', () => { resetConfirm.hidden = true; });
  $('#btn-reset-yes').addEventListener('click', () => {
    settings.reset();
    resetConfirm.hidden = true;
    toast('Settings reset.');
  });

  settings.addEventListener('change', fill);
  fill();
  return { onShow() { fill(); fillMics(); } };
}
