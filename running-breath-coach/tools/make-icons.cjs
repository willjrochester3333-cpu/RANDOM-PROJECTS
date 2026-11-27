// Renders the PNG app icons from icons/icon.svg with the local Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const dir = path.join(__dirname, '..', 'app', 'icons');
  const svg = fs.readFileSync(path.join(dir, 'icon.svg'), 'utf8');
  const maskable = svg.replace('rx="112"', 'rx="0"').replace('r="170"', 'r="150"').replace(/M84 256c36 0 46-96 88-96s50 192 84 192 46-192 84-192 52 96 88 96/, 'M116 256c29 0 37-78 71-78s40 156 69 156 37-156 69-156 42 78 71 78');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const shots = [['icon-192.png', 192, svg], ['icon-512.png', 512, svg], ['apple-touch-icon.png', 180, maskable], ['icon-maskable-512.png', 512, maskable]];
  for (const [name, size, src] of shots) {
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(`<html><body style="margin:0;background:transparent">${src.replace('<svg ', `<svg width="${size}" height="${size}" `)}</body></html>`);
    await page.screenshot({ path: path.join(dir, name), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  }
  await browser.close();
  console.log('icons written to', dir);
})();
