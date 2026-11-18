"""Compares language models on this Pi: how soon each one starts answering, how fast it
writes, and how many everyday questions it gets right, using exactly Jarvis's own prompt and
settings (including reading ahead while you speak).

On the server:  bash ~/jarvis/core/bench.sh                  the usual small models
                bash ~/jarvis/core/bench.sh qwen2.5:1.5b     just these, plus your current model
Models that weren't on the Pi before are deleted again afterwards; add --keep to keep them.
"""
import asyncio
import json
import re
import statistics
import sys
import time

import httpx

from .chat import (ANSWER_OPTIONS, OLLAMA_LOAD_OPTIONS, OLLAMA_MODEL, OLLAMA_URL, SYSTEM, Chunker,
                   _user_content, speakable)
from .report import base, clock_text

CANDIDATES = ["llama3.2:1b", "llama3.2:1b-instruct-q4_K_M", "qwen2.5:1.5b", "gemma3:1b"]

# Settled facts with one clear answer, so "right" is easy to check.
QUESTIONS = [
    ("What is the capital of Australia?", r"canberra"),
    ("Who wrote Romeo and Juliet?", r"shakespeare"),
    ("How many legs does a spider have?", r"\b(eight|8)\b"),
    ("Which planet is known as the Red Planet?", r"\bmars\b"),
    ("What is the largest ocean on Earth?", r"pacific"),
    ("Who painted the Mona Lisa?", r"leonardo|da vinci"),
    ("What is the chemical symbol for gold?", r"\bau\b"),
    ("In which country are the pyramids of Giza?", r"egypt"),
    ("Who was the first person to walk on the Moon?", r"armstrong"),
    ("What language is spoken in Brazil?", r"portuguese"),
    ("In what year did the Second World War end?", r"1945"),
    ("What gas do plants take in from the air?", r"carbon dioxide|co2|co₂"),
    ("How many minutes are there in a day?", r"1,?440"),
    ("What is the freezing point of water in Fahrenheit?", r"\b32\b"),
]

# A typical house report, so the prompt is the size Jarvis really sends.
SNAPSHOT = {"weather": {"temp_c": 8.4, "humidity": 71, "pressure_hpa": 1009, "age_s": 60, "stale": False},
            "dinner": {"state": "idle"}}


def say(text: str = "") -> None:
    print(text, flush=True)


async def installed(http: httpx.AsyncClient) -> dict[str, int]:
    r = await http.get("/api/tags")
    r.raise_for_status()
    return {m["name"]: m.get("size", 0) for m in r.json().get("models", [])}


def find(name: str, have: dict[str, int]) -> str | None:
    full = name if ":" in name else name + ":latest"
    return full if full in have else None


async def pull(http: httpx.AsyncClient, name: str) -> bool:
    say(f"  downloading {name} ...")
    shown = -1
    async with http.stream("POST", "/api/pull", json={"model": name, "stream": True}, timeout=None) as r:
        async for line in r.aiter_lines():
            if not line:
                continue
            msg = json.loads(line)
            if "error" in msg:
                say(f"  could not download {name}: {msg['error']}")
                return False
            total, done = msg.get("total"), msg.get("completed")
            if total and done is not None:
                tenth = int(10 * done / total)
                if tenth > shown:
                    shown = tenth
                    say(f"    {10 * tenth}% of {total / 1e9:.1f} GB")
    return True


async def chat(http: httpx.AsyncClient, model: str, messages: list, options: dict, stream: bool):
    body = {"model": model, "messages": messages, "options": options, "stream": stream, "keep_alive": -1}
    if not stream:
        r = await http.post("/api/chat", json=body, timeout=600)
        r.raise_for_status()
        return r.json()
    return http.stream("POST", "/api/chat", json=body, timeout=600)


async def ask(http: httpx.AsyncClient, model: str, question: str) -> dict:
    """One question the way Jarvis asks it: read ahead first, then the question alone."""
    report = base(SNAPSHOT, clock_text())
    system = {"role": "system", "content": SYSTEM}
    ahead = await chat(http, model, [system, {"role": "user", "content": _user_content(report, None)}],
                       {**OLLAMA_LOAD_OPTIONS, "num_predict": 1}, stream=False)
    t0 = time.monotonic()
    first_piece, text, stats = None, "", {}
    chunker = Chunker()
    async with await chat(http, model, [system, {"role": "user", "content": _user_content(report, question)}],
                          ANSWER_OPTIONS, stream=True) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line:
                continue
            msg = json.loads(line)
            if msg.get("done"):
                stats = msg
            piece = msg.get("message", {}).get("content", "")
            text += piece
            if piece and first_piece is None and chunker.feed(piece):
                first_piece = time.monotonic() - t0
    total = time.monotonic() - t0
    return {"answer": speakable(text), "first": first_piece if first_piece is not None else total, "total": total,
            "write_rate": stats.get("eval_count", 0) / max(stats.get("eval_duration", 0) / 1e9, 1e-3),
            "read_rate": ahead.get("prompt_eval_count", 0) / max(ahead.get("prompt_eval_duration", 0) / 1e9, 1e-3)}


async def bench(model: str, http: httpx.AsyncClient) -> dict | None:
    say(f"\n{model}")
    t0 = time.monotonic()
    try:
        await chat(http, model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Hello."}],
                   {**OLLAMA_LOAD_OPTIONS, "num_predict": 1}, stream=False)
    except httpx.HTTPError as e:
        say(f"  could not load {model}: {e}")
        return None
    say(f"  loaded in {time.monotonic() - t0:.0f} s")
    results = []
    for question, right in QUESTIONS:
        res = await ask(http, model, question)
        res["right"] = re.search(right, res["answer"].lower()) is not None
        results.append(res)
        say(f"  {'right' if res['right'] else 'WRONG'}  {res['first']:4.1f} s  {question}  ->  {res['answer'][:70]}")
    return {"model": model, "right": sum(r["right"] for r in results),
            "first": statistics.median(r["first"] for r in results),
            "total": statistics.median(r["total"] for r in results),
            "write": statistics.mean(r["write_rate"] for r in results),
            "read": statistics.mean(r["read_rate"] for r in results)}


async def main(args: list[str]) -> None:
    keep = "--keep" in args
    names = [a for a in args if not a.startswith("--")] or CANDIDATES
    models = [OLLAMA_MODEL] + [n for n in names if n != OLLAMA_MODEL]
    say(f"Comparing {len(models)} models on {len(QUESTIONS)} questions, with Jarvis's own prompt "
        f"({OLLAMA_LOAD_OPTIONS['num_thread']} processor cores).")
    rows, sizes = [], {}
    async with httpx.AsyncClient(base_url=OLLAMA_URL, timeout=600) as http:
        before = await installed(http)
        for name in models:
            pulled = False
            if not find(name, before):
                if not await pull(http, name):
                    continue
                pulled = True
            have = await installed(http)
            sizes[name] = have.get(find(name, have) or name, 0)
            row = await bench(name, http)
            if row:
                rows.append(row)
            if pulled and not keep and name != OLLAMA_MODEL:
                await http.request("DELETE", "/api/delete", json={"model": name})
                say(f"  removed {name} again (add --keep to keep downloaded models)")
    if not rows:
        say("\nNo model could be tested.")
        return
    say(f"\n{'model':30} {'size':>7} {'first words':>12} {'whole answer':>13} {'writes':>9} {'reads':>9} {'right':>7}")
    for r in sorted(rows, key=lambda r: (-r["right"], r["first"])):
        mark = "  <- now" if r["model"] == OLLAMA_MODEL else ""
        say(f"{r['model']:30} {sizes.get(r['model'], 0) / 1e9:5.1f} GB {r['first']:10.1f} s {r['total']:11.1f} s "
            f"{r['write']:6.1f}/s {r['read']:6.0f}/s {r['right']:3}/{len(QUESTIONS)}{mark}")
    say("\nfirst words: from the end of the question to the first piece Jarvis can say (median)."
        "\nwrites / reads: tokens per second while writing the answer / reading the report.")
    best = max(rows, key=lambda r: (r["right"], -r["first"]))
    if best["model"] != OLLAMA_MODEL:
        say(f"\nMost right answers, quickest among those: {best['model']}. To use it, set "
            f"OLLAMA_MODEL={best['model']} in ~/jarvis/core/.env and run: bash ~/jarvis/core/setup.sh")
    else:
        say(f"\nYour current model, {OLLAMA_MODEL}, is the best of these.")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
