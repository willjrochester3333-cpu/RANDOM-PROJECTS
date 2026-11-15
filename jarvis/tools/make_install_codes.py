#!/usr/bin/env python3
"""Builds one paste-able install block per Raspberry Pi.

Each block is a gzipped tar of that Pi's folder, base64-encoded inside a shell
here-document. Base64 has no characters a terminal or bash can mangle (no `!`,
tabs or quotes), and gzip's checksum makes a damaged paste fail loudly instead
of leaving broken code behind.

Run from anywhere:  python3 jarvis/tools/make_install_codes.py
"""
import base64
import html
import io
import tarfile
from pathlib import Path

JARVIS = Path(__file__).resolve().parent.parent
OUT = JARVIS / "install-codes"
SKIP_NAMES = {".env", "passwd", "__pycache__", ".pytest_cache", "config.py"}
SKIP_SUFFIXES = {".db", ".pyc"}

PIS = {
    "core": {
        "title": "CORE server (Raspberry Pi 5)",
        "after": "cd ~/jarvis/core && bash setup.sh",
        "then": "Setup starts by itself and takes 10 to 20 minutes the first time. Pasting it "
                "again later updates the server and keeps your password. At the end it prints the "
                "MQTT password: copy it somewhere safe, every other device needs it. Then type "
                "hostname -I to get the server's IP address and open http://THAT-ADDRESS/ in a "
                "browser to see the dashboard.",
    },
    "outpost": {
        "title": "OUTPOST weather station (Raspberry Pi 3)",
        "after": 'echo "Copied. Now run: bash ~/jarvis/outpost/install.sh YOUR-MQTT-PASSWORD SERVER-IP"',
        "then": "After the paste, run the install line it prints, with the MQTT password and "
                "the server's IP address in place of YOUR-MQTT-PASSWORD and SERVER-IP. "
                "Then reboot with: sudo reboot",
    },
    "console": {
        "title": "CONSOLE touchscreen (Raspberry Pi 5)",
        "after": 'echo "Copied. Now run: bash ~/jarvis/console/install.sh YOUR-MQTT-PASSWORD SERVER-IP"',
        "then": "After the paste, run the install line it prints, with the MQTT password and "
                "the server's IP address in place of YOUR-MQTT-PASSWORD and SERVER-IP. "
                "Then reboot with: sudo reboot. "
                "It comes back up showing the dashboard full screen.",
    },
    "camera": {
        "title": "CAMERA (any Pi with a camera module)",
        "after": 'echo "Copied. Now run: bash ~/jarvis/camera/install.sh YOUR-MQTT-PASSWORD SERVER-IP"',
        "then": "Paste this on whichever Pi has the camera plugged in, then run the install line "
                "it prints, with the MQTT password and the server's IP address. No reboot needed: "
                "a Camera panel appears on the dashboard within a few seconds.",
    },
}


def wanted(path: Path) -> bool:
    return not any(p in SKIP_NAMES for p in path.parts) and path.suffix not in SKIP_SUFFIXES


def bundle(folder: str) -> bytes:
    buf = io.BytesIO()
    src = JARVIS / folder
    files = sorted(p for p in src.rglob("*") if p.is_file() and wanted(p.relative_to(src)))
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tar:
        for f in files:
            info = tarfile.TarInfo(f"jarvis/{folder}/{f.relative_to(src).as_posix()}")
            data = f.read_bytes()
            info.size = len(data)
            info.mode = 0o755 if f.suffix == ".sh" else 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


PAGE = """<title>J.A.R.V.I.S. Install Codes</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Layout: one column; a short how-to, then one block per Pi with a single Copy button. */
:root {
  --bg: #f1f4f8; --panel: #ffffff; --ink: #15202f; --muted: #566579; --line: #cbd4e0;
  --accent: #a9690a; --on-accent: #ffffff; --ok: #1f7a4d;
  --display: "Space Grotesk", "Segoe UI", system-ui, sans-serif;
  --body: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0d1520; --panel: #142032; --ink: #e4ebf4; --muted: #94a4b9; --line: #2b3b53;
  --accent: #f0b23a; --on-accent: #1a1305; --ok: #4cc38a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0d1520; --panel: #142032; --ink: #e4ebf4; --muted: #94a4b9; --line: #2b3b53;
  --accent: #f0b23a; --on-accent: #1a1305; --ok: #4cc38a; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 16px/1.6 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 36px 64px; }
.wrap { max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px; }
h1, h2 { font-family: var(--display); margin: 0; line-height: 1.2; text-wrap: balance; }
h1 { font-size: clamp(1.8rem, 5vw, 2.4rem); }
h2 { font-size: 1.2rem; }
p { margin: 0; max-width: 66ch; }
.muted { color: var(--muted); }
ol { margin: 0; padding-left: 1.3em; display: flex; flex-direction: column; gap: 6px; }
kbd, code { font-family: var(--mono); font-size: 0.88em; }
kbd { border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 4px; padding: 0 5px; background: var(--panel); }
.pi { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 20px; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.size { font: 0.8rem var(--mono); color: var(--muted); }
button { font: 600 1rem var(--body); background: var(--accent); color: var(--on-accent); border: 0; border-radius: 6px; padding: 10px 22px; cursor: pointer; min-width: 9em; }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
button.done { background: var(--ok); color: var(--panel); }
details summary { cursor: pointer; color: var(--muted); font-size: 0.9rem; }
pre { margin: 8px 0 0; max-height: 220px; overflow: auto; font: 11px/1.45 var(--mono); background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 10px; white-space: pre; user-select: all; }
</style>

<div class="wrap">
  <header style="display:flex;flex-direction:column;gap:10px">
    <h1>J.A.R.V.I.S. Install Codes</h1>
    <p>One paste puts all of a Pi's J.A.R.V.I.S. files on it. The block is compressed, so it looks like random letters; the readable code is in the <code>jarvis/</code> folder on GitHub. If any part of the paste goes missing, it stops with an error instead of installing broken code.</p>
  </header>
  <section style="display:flex;flex-direction:column;gap:10px">
    <h2>How to use</h2>
    <ol>
      <li>Open the Pi's terminal in Raspberry Pi Connect.</li>
      <li>Click <b>Copy</b> on the block for that Pi below.</li>
      <li>Click in the terminal and paste with <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>V</kbd> or right-click, Paste. If the browser asks to allow the clipboard, allow it.</li>
      <li>Press <kbd>Enter</kbd> if nothing starts by itself.</li>
    </ol>
  </section>
  __BLOCKS__
</div>

<script>
document.querySelectorAll("button[data-copy]").forEach(btn => {
  btn.addEventListener("click", async () => {
    const pre = document.getElementById(btn.dataset.copy);
    try {
      await navigator.clipboard.writeText(pre.textContent);
      btn.textContent = "Copied";
      btn.classList.add("done");
      setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("done"); }, 2500);
    } catch {
      pre.closest("details").open = true;
      const r = document.createRange(); r.selectNodeContents(pre);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      btn.textContent = "Selected: press Ctrl+C";
    }
  });
});
</script>
"""

BLOCK = """<section class="pi" aria-labelledby="h-{id}">
    <div class="row"><h2 id="h-{id}">{title}</h2><button type="button" id="copy-{id}" data-copy="code-{id}">Copy</button></div>
    <p>{then}</p>
    <details><summary>Show the block ({lines} lines)</summary><pre id="code-{id}">{code}</pre></details>
  </section>"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    blocks = []
    for folder, meta in PIS.items():
        b64 = base64.b64encode(bundle(folder)).decode()
        lines = [b64[i:i + 76] for i in range(0, len(b64), 76)]
        text = (
            f"cd ~ && base64 -d <<'JARVIS_END' | tar -xz && {meta['after']}\n"
            + "\n".join(lines)
            + "\nJARVIS_END\n"
        )
        (OUT / f"{folder}.txt").write_text(text)
        blocks.append(BLOCK.format(id=folder, title=html.escape(meta["title"]), then=html.escape(meta["then"]),
                                   lines=len(lines) + 2, code=html.escape(text)))
        print(f"{folder}: {len(text)} bytes, {len(lines) + 2} lines")
    (OUT / "index.html").write_text(PAGE.replace("__BLOCKS__", "\n  ".join(blocks)))


if __name__ == "__main__":
    main()
