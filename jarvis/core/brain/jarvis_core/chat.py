"""Answers questions, typed or spoken.

CHAT_BACKEND picks who answers:
  ollama   a local model running on this Pi (default, needs no internet)
  claude   the Anthropic API (needs ANTHROPIC_API_KEY)
  builtin  canned answers about the weather and dinner only
"""
import asyncio
import logging
import os
import time
from collections import deque

import httpx

log = logging.getLogger("jarvis.chat")

BACKEND = os.environ.get("CHAT_BACKEND", "ollama").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
CLAUDE_MODEL = "claude-opus-5-5"
MAX_REPLY_TOKENS = 160

SYSTEM = """You are J.A.R.V.I.S., the assistant for one household. Your replies are read aloud \
by a speaker and shown on a small screen, so answer in one to three short spoken sentences. \
No markdown, no lists, no emoji. Be dry, calm and precise. If asked to control something in \
the house, say you cannot do that yet. Use the house report below when the question is about \
the house; otherwise ignore it."""


def describe(snapshot: dict) -> str:
    """The house state as a few plain sentences, which small models follow better than JSON."""
    parts = []
    w = snapshot.get("weather")
    if w:
        mins = w["age_s"] // 60
        when = "just now" if mins < 1 else f"{mins} minutes ago"
        stale = " This reading is old; the station may be down." if w["stale"] else ""
        parts.append(f"Outside: {w['temp_c']:.1f} degrees C, {w['humidity']:.0f} percent humidity, "
                     f"{w['pressure_hpa']:.0f} hectopascals, measured {when}.{stale}")
    else:
        parts.append("Outside: no reading from the weather station yet.")
    d = snapshot.get("dinner", {})
    parts.append({"idle": "Dinner has not been called.",
                  "calling": "Dinner is ready and nobody has answered yet.",
                  "acknowledged": "Dinner is ready and someone has said they are on their way."}
                 .get(d.get("state"), "Dinner: unknown."))
    nodes = snapshot.get("nodes", {})
    on = sorted(n for n, s in nodes.items() if s.get("online"))
    off = sorted(n for n, s in nodes.items() if not s.get("online"))
    if on:
        parts.append("Devices online: " + ", ".join(on) + ".")
    if off:
        parts.append("Devices offline: " + ", ".join(off) + ".")
    parts.append("Time: " + time.strftime("%A %H:%M"))
    return " ".join(parts)


class Chat:
    def __init__(self, house):
        self.house = house
        self.history: deque[dict] = deque(maxlen=10)
        self.backend = BACKEND
        self.client = None
        if self.backend == "claude":
            if os.environ.get("ANTHROPIC_API_KEY"):
                import anthropic
                self.client = anthropic.AsyncAnthropic()
            else:
                log.warning("CHAT_BACKEND=claude but ANTHROPIC_API_KEY is empty; using builtin answers")
                self.backend = "builtin"
        elif self.backend == "ollama":
            self.http = httpx.AsyncClient(base_url=OLLAMA_URL, timeout=httpx.Timeout(240, connect=5))
        log.info("chat backend: %s", self.backend)

    async def start(self) -> None:
        """Call once the event loop is running."""
        if self.backend == "ollama":
            asyncio.create_task(self._warm_up())

    async def ask(self, text: str) -> str:
        text = text.strip()
        if self.backend == "ollama":
            return await self._ollama(text)
        if self.backend == "claude":
            return await self._claude(text)
        return self._builtin(text)

    def _remember(self, text: str, reply: str) -> None:
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})

    # ---- Ollama ----

    async def _warm_up(self) -> None:
        """Load the model into memory at startup, so the first question is not slow."""
        for attempt in range(30):
            try:
                r = await self.http.post("/api/generate", json={"model": OLLAMA_MODEL, "keep_alive": "24h"})
                if r.status_code == 200:
                    log.info("ollama model %s loaded", OLLAMA_MODEL)
                    return
                log.warning("ollama: %s", r.text[:200])
                return
            except httpx.HTTPError:
                await asyncio.sleep(10)   # ollama is still starting

    async def _ollama(self, text: str) -> str:
        system = SYSTEM + "\n\nHouse report: " + describe(self.house.snapshot())
        body = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "keep_alive": "24h",
            "options": {"num_predict": MAX_REPLY_TOKENS, "temperature": 0.6, "num_ctx": 2048},
            "messages": [{"role": "system", "content": system}, *self.history, {"role": "user", "content": text}],
        }
        try:
            r = await self.http.post("/api/chat", json=body)
        except httpx.ConnectError:
            return "The language model service is not running on the server."
        except httpx.TimeoutException:
            return "The language model took too long to answer."
        if r.status_code == 404:
            return (f"The model {OLLAMA_MODEL} is not downloaded yet. On the server, run: "
                    f"sudo docker compose exec ollama ollama pull {OLLAMA_MODEL}")
        if r.status_code != 200:
            log.error("ollama %s: %s", r.status_code, r.text[:300])
            return "The language model returned an error."
        reply = r.json().get("message", {}).get("content", "").strip()
        reply = " ".join(reply.split())
        if not reply:
            return "I have no answer for that."
        self._remember(text, reply)
        return reply

    # ---- Claude ----

    async def _claude(self, text: str) -> str:
        import anthropic

        state = describe(self.house.snapshot())
        messages = [*self.history, {"role": "user", "content": f"<house_report>{state}</house_report>\n\n{text}"}]
        try:
            response = await self.client.beta.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=16000,
                system=SYSTEM,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=messages,
            )
        except anthropic.AuthenticationError:
            return "My API key was rejected. Check ANTHROPIC_API_KEY in the server's .env file."
        except anthropic.RateLimitError:
            return "I am being rate limited. Try again in a minute."
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            return "The language service returned an error. Try again shortly."
        except anthropic.APIConnectionError:
            return "I cannot reach the internet right now."
        if response.stop_reason == "refusal":
            return "I can't help with that one."
        reply = " ".join(b.text for b in response.content if b.type == "text").strip()
        if not reply:
            return "I have no answer for that."
        self._remember(text, reply)
        return reply

    # ---- builtin ----

    def _builtin(self, text: str) -> str:
        q = text.lower()
        snap = self.house.snapshot()
        if any(w in q for w in ("weather", "outside", "temperature", "cold", "warm", "hot", "humid", "pressure")):
            w = snap["weather"]
            if not w:
                return "I have no reading from the outdoor station yet."
            old = " That reading is out of date." if w["stale"] else ""
            return (f"Outside it is {w['temp_c']:.1f} degrees, {w['humidity']:.0f} percent humidity, "
                    f"pressure {w['pressure_hpa']:.0f} hectopascals.{old}")
        if "dinner" in q:
            return {"idle": "Dinner has not been called.",
                    "calling": "Dinner is ready and waiting for you.",
                    "acknowledged": "Dinner is ready. The kitchen knows you are on your way."}[snap["dinner"]["state"]]
        return "I can only answer about the weather and dinner in this mode."
