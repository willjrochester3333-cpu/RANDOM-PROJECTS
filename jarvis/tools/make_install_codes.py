#!/usr/bin/env python3
"""Builds the install page: one short line per Raspberry Pi to paste into its terminal.

Each line downloads this branch from GitHub (the repository must be public), unpacks only
that Pi's folder into ~/jarvis/ and starts its installer. Settings files such as .env are
not in the repository, so an update never touches them. A short line pastes reliably in
Raspberry Pi Connect, where large pasted blocks crash the terminal.

Run from anywhere:  python3 jarvis/tools/make_install_codes.py
"""
import html
from pathlib import Path

JARVIS = Path(__file__).resolve().parent.parent
OUT = JARVIS / "install-codes"
REPO = "willjrochester3333-cpu/RANDOM-PROJECTS"
BRANCH = "claude/peaceful-mayer-pfwzre"
DOWNLOAD = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.tar.gz"
PIS = {
    "core": {
        "title": "CORE server (Raspberry Pi 5)",
        "after": "cd ~/jarvis/core && bash setup.sh",
        "then": "Setup starts by itself and takes 10 to 20 minutes the first time. Pasting it "
                "again later updates the server and keeps your password. At the end it prints the "
                "MQTT password: copy it somewhere safe, every other device needs it. Then type "
                "hostname -I to get the server's IP address and open http://THAT-ADDRESS/ in a "
                "browser to see the dashboard. With a USB microphone and speaker plugged in, "
                "say 'Hey Jarvis' once it is done. For internet answers to any question, then "
                "run: bash ~/jarvis/core/set-key.sh and paste your Anthropic API key (from "
                "platform.claude.com); it doesn't show on screen.",
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
    "core/voice": {
        "title": "VOICE update (server only, quick)",
        "after": "sudo install -m 755 ~/jarvis/core/voice/voice.py /opt/jarvis/voice.py && sudo systemctl restart jarvis-voice && echo 'Voice service updated'",
        "then": "Updates only the microphone and speaker service on the server and restarts it, in a "
                "few seconds. Use this instead of the full CORE block when only the voice changed.",
    },
    "core/speech": {
        "title": "SPEECH update (server only, quick)",
        "after": "cd ~/jarvis/core && sudo docker compose up -d --build speech && echo 'Speech service updated'",
        "then": "Rebuilds only the hearing-and-voice container on the server, about a minute. Use "
                "this instead of the full CORE block when only the speech service changed.",
    },
    "camera": {
        "title": "CAMERA (any Pi with a camera module)",
        "after": 'echo "Copied. Now run: bash ~/jarvis/camera/install.sh YOUR-MQTT-PASSWORD SERVER-IP"',
        "then": "Paste this on whichever Pi has the camera plugged in, then run the install line "
                "it prints, with the MQTT password and the server's IP address. No reboot needed: "
                "a Camera panel appears on the dashboard within a few seconds.",
    },
}


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
pre.cmd { max-height: none; white-space: pre-wrap; word-break: break-all; font-size: 12px; margin: 0; }
pre { margin: 8px 0 0; max-height: 220px; overflow: auto; font: 11px/1.45 var(--mono); background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 10px; white-space: pre; user-select: all; }
</style>

<div class="wrap">
  <header style="display:flex;flex-direction:column;gap:10px">
    <h1>J.A.R.V.I.S. Install Codes</h1>
    <p>One short line per Pi. The Pi downloads its J.A.R.V.I.S. files from GitHub itself and installs them, so nothing big goes through the paste. Your settings (passwords, API key) stay as they are. The GitHub repository has to be public for the download to work.</p>
  </header>
  <section style="display:flex;flex-direction:column;gap:10px">
    <h2>How to use</h2>
    <ol>
      <li>Open the Pi's terminal in Raspberry Pi Connect.</li>
      <li>Click <b>Copy</b> on the line for that Pi below.</li>
      <li>Click in the terminal and paste with <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>V</kbd> or right-click, Paste. If the browser asks to allow the clipboard, allow it.</li>
      <li>Press <kbd>Enter</kbd>.</li>
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
      const d = pre.closest("details"); if (d) d.open = true;
      const r = document.createRange(); r.selectNodeContents(pre);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      btn.textContent = "Selected: press Ctrl+C";
    }
  });
});
</script>
"""

CMD_BLOCK = """<section class="pi" aria-labelledby="h-{id}">
    <div class="row"><h2 id="h-{id}">{title}</h2><button type="button" id="copy-{id}" data-copy="code-{id}">Copy</button></div>
    <p>{then}</p>
    <pre class="cmd" id="code-{id}">{code}</pre>
  </section>"""

BLOCK = """<section class="pi" aria-labelledby="h-{id}">
    <div class="row"><h2 id="h-{id}">{title}</h2><button type="button" id="copy-{id}" data-copy="code-{id}">Copy</button></div>
    <p>{then}</p>
    <details><summary>Show the block ({lines} lines)</summary><pre id="code-{id}">{code}</pre></details>
  </section>"""


# Microcontroller files are loaded with Thonny, so they go on the page as plain text to paste
# into a new Thonny file and save to the board.
THONNY_FILES = [
    ("kitchen/main.py", "KITCHEN CAMERA: main.py (for Thonny)",
     "Copy, paste into a new file in Thonny, and save it to the board as main.py. "
     "Flash the camera firmware first (SETUP.md, section 2)."),
    ("kitchen/config.example.py", "KITCHEN CAMERA: config.py (for Thonny)",
     "Copy, paste into a new file in Thonny, fill in your Wi-Fi and the server's details, and "
     "save it to the board as config.py."),
]


def command(folder: str, after: str) -> str:
    """Download, unpack only jarvis/<folder>, then run the Pi's next step."""
    return (f"if curl -fsSL {DOWNLOAD} | tar -xz -C ~ --strip-components=1 --wildcards '*/jarvis/{folder}'; "
            f"then {after}; else echo 'Download failed: is the GitHub repository public, and is this Pi online?'; fi")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    blocks = []
    for folder, meta in PIS.items():
        name = folder.replace("/", "-")
        cmd = command(folder, meta["after"])
        (OUT / f"{name}.txt").write_text(cmd + "\n")
        blocks.append(CMD_BLOCK.format(id=name, title=html.escape(meta["title"]), then=html.escape(meta["then"]),
                                       code=html.escape(cmd)))
        print(f"{folder}: {len(cmd)} characters")
    for path, title, then in THONNY_FILES:
        text = (JARVIS / path).read_text()
        blocks.append(BLOCK.format(id=path.replace("/", "-").replace(".", "-"), title=html.escape(title),
                                   then=html.escape(then), lines=text.count("\n"), code=html.escape(text)))
    (OUT / "index.html").write_text(PAGE.replace("__BLOCKS__", "\n  ".join(blocks)))


if __name__ == "__main__":
    main()
