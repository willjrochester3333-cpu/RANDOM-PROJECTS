"""Answers questions, typed or spoken.

CHAT_BACKEND picks who answers:
  ollama   a local model running on this Pi (default, needs no internet)
  claude   the Anthropic API (needs ANTHROPIC_API_KEY)
  builtin  canned answers about the weather and dinner only
"""
import asyncio
import json
import logging
import os
import re
from collections import deque
from typing import Awaitable, Callable

import httpx

from .report import Forecast, describe

log = logging.getLogger("jarvis.chat")

BACKEND = os.environ.get("CHAT_BACKEND", "ollama").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
CLAUDE_MODEL = "claude-opus-5-5"
MAX_REPLY_TOKENS = 160

SYSTEM = """You are J.A.R.V.I.S., the assistant for one household. Your replies are read aloud \
by a speaker and shown on a small screen, so answer in one to three short spoken sentences. \
No markdown, no lists, no emoji. Be dry, calm and precise. If asked to control something in \
the house, say you cannot do that yet. Each question comes with a house report: the date and \
time, our own weather station's readings, the forecast, dinner, and which devices are online. \
Use it for anything about the house, the weather or the time, and ignore it otherwise. Never \
read the whole report out; answer only what was asked."""

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
OnSentence = Callable[[str], Awaitable[None]]


class Chat:
    def __init__(self, house):
        self.house = house
        self.history: deque[dict] = deque(maxlen=10)
        self.forecast = Forecast()
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
        asyncio.create_task(self.forecast.refresh())

    async def report(self) -> str:
        await self.forecast.refresh()
        history = await asyncio.to_thread(self.house.store.history, 24, 48)
        return describe(self.house.snapshot(), history, self.forecast)

    async def ask(self, text: str, on_sentence: OnSentence | None = None) -> str:
        """Answer the question. If on_sentence is given, each finished sentence is passed to it
        as soon as it exists, so speech can start before the whole answer is written."""
        text = text.strip()
        if self.backend == "ollama":
            reply = await self._ollama(text, on_sentence)
            return reply
        reply = await self._claude(text) if self.backend == "claude" else self._builtin(text)
        if on_sentence:
            await on_sentence(reply)
        return reply

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

    async def _ollama(self, text: str, on_sentence: OnSentence | None) -> str:
        # The report goes with the question, after the history, so the fixed system prompt and
        # the earlier turns stay cached inside Ollama between questions (much faster on a Pi).
        question = f"House report: {await self.report()}\n\nQuestion: {text}"
        body = {
            "model": OLLAMA_MODEL,
            "stream": True,
            "keep_alive": "24h",
            "options": {"num_predict": MAX_REPLY_TOKENS, "temperature": 0.5, "num_ctx": 3072},
            "messages": [{"role": "system", "content": SYSTEM}, *self.history, {"role": "user", "content": question}],
        }
        reply, pending = "", ""
        try:
            async with self.http.stream("POST", "/api/chat", json=body) as r:
                if r.status_code == 404:
                    return (f"The model {OLLAMA_MODEL} is not downloaded yet. On the server, run: "
                            f"sudo docker compose exec ollama ollama pull {OLLAMA_MODEL}")
                if r.status_code != 200:
                    log.error("ollama %s: %s", r.status_code, (await r.aread())[:300])
                    return "The language model returned an error."
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    piece = json.loads(line).get("message", {}).get("content", "")
                    reply += piece
                    pending += piece
                    if on_sentence:
                        *done, pending = SENTENCE_END.split(pending)
                        for sentence in done:
                            if sentence.strip():
                                await on_sentence(" ".join(sentence.split()))
        except httpx.ConnectError:
            return "The language model service is not running on the server."
        except httpx.TimeoutException:
            return "The language model took too long to answer."
        reply = " ".join(reply.split())
        if not reply:
            return "I have no answer for that."
        if on_sentence and pending.strip():
            await on_sentence(" ".join(pending.split()))
        self._remember(text, reply)
        return reply

    # ---- Claude ----

    async def _claude(self, text: str) -> str:
        import anthropic

        state = await self.report()
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
