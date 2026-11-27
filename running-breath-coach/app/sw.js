// Offline support: cache the app shell so BreathPace works with no signal.
// Bump VERSION whenever files change so phones pick up the new build.
const VERSION = 'breathpace-v1';
const SHELL = [
  './',
  'index.html',
  'styles.css',
  'manifest.webmanifest',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png',
  'icons/icon-maskable-512.png',
  'fonts/barlow-condensed-latin-600-normal.woff2',
  'fonts/barlow-condensed-latin-700-normal.woff2',
  'fonts/barlow-latin-400-normal.woff2',
  'fonts/barlow-latin-600-normal.woff2',
  'js/main.js',
  'js/engine.js',
  'js/analysis.js',
  'js/audio/capture-worklet.js',
  'js/audio/sources.js',
  'js/audio/wav.js',
  'js/coach/coach.js',
  'js/coach/feedback.js',
  'js/coach/phrases.js',
  'js/dsp/biquad.js',
  'js/dsp/breath-detector.js',
  'js/dsp/cadence.js',
  'js/dsp/frontend.js',
  'js/dsp/periodicity.js',
  'js/dsp/ring-buffer.js',
  'js/sim/breath-synth.js',
  'js/store/settings.js',
  'js/ui/charts.js',
  'js/ui/check-view.js',
  'js/ui/dom.js',
  'js/ui/history-view.js',
  'js/ui/run-stats.js',
  'js/ui/run-view.js',
  'js/ui/setup-view.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Network first (so updates arrive when online), falling back to the cache.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req, { ignoreSearch: true }).then((hit) => hit || caches.match('index.html'))),
  );
});
