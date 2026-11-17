"""Answers questions, typed or spoken.

CHAT_BACKEND picks who answers:
  ollama   a local model running on this Pi (default, needs no internet)
  claude   the Anthropic API (needs ANTHROPIC_API_KEY)
  builtin  canned answers about the weather and dinner only

Speed on a Raspberry Pi comes from four things here:
  * a small model (OLLAMA_MODEL);
  * Ollama's prompt cache: every request starts with exactly the text of the previous one
    (the same system prompt, then the conversation so far, word for word), so the model only
    reads the new question. The conversation is forgotten after a few quiet minutes, or once
    it gets long, which keeps that text short;
  * the same model settings on every request, including the warm-up, so Ollama never reloads;
  * streaming: each sentence is handed on for speaking as soon as it is written.
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Awaitable, Callable

import httpx

from .report import Forecast, describe

log = logging.getLogger("jarvis.chat")

BACKEND = os.environ.get("CHAT_BACKEND", "ollama").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_THREADS = int(os.environ.get("OLLAMA_THREADS", "3"))
MAX_REPLY_TOKENS = int(os.environ.get("MAX_REPLY_TOKENS", "400"))
CLAUDE_MODEL = "claude-opus-5-5"

FORGET_AFTER_S = 180          # a pause this long starts a new conversation
MAX_HISTORY_CHARS = 3500      # about 900 tokens; longer starts a new conversation

# Settings Ollama loads the model with. They must be identical on every request, or Ollama
# reloads the model and throws its cache away. One core is left for the camera and speech.
OLLAMA_LOAD_OPTIONS = {"num_ctx": 2048, "num_thread": OLLAMA_THREADS}

SYSTEM = """You are J.A.R.V.I.S., the assistant for one household. Your replies are read aloud \
by a speaker and shown on a small screen. Answer in one or two short spoken sentences, and only \
give more detail when asked for it. No markdown, no lists, no emoji. Be dry, calm and precise. \
If asked to control something in the house, say you cannot do that yet. Each question comes \
with a house report: the date and time, our own weather station's readings, the forecast, \
dinner, and which devices are online. Use it for anything about the house, the weather or the \
time, and ignore it otherwise. Never read the whole report out; answer only what was asked."""

CUT_SHORT = "I'll stop there. Say go on if you want more."

OnSentence = Callable[[str], Awaitable[None]]

_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_MARKDOWN = re.compile(r"^\s*(?:[-*•]|#+)\s+|[*_`#]+", re.M)


def speakable(text: str) -> str:
    """Text as it should be spoken and shown: no markdown symbols, single spaces."""
    return " ".join(_MARKDOWN.sub("", text).split())


class Chunker:
    """Cuts streamed text into pieces worth speaking: whole sentences, or the start of a very
    long sentence at a comma, so the speaker never waits long for the first words."""

    LONG = 160

    def __init__(self):
        self.buf = ""

    def feed(self, piece: str) -> list[str]:
        self.buf += piece
        *parts, self.buf = _BREAK.split(self.buf)
        if len(self.buf) > self.LONG:
            cut = self.buf.rfind(", ", 0, self.LONG)
            if cut > 40:
                parts.append(self.buf[:cut + 1])
                self.buf = self.buf[cut + 2:]
        return [p for p in parts if p.strip()]

    def rest(self) -> str:
        rest, self.buf = self.buf, ""
        return rest


class Chat:
    def __init__(self, house):
        self.house = house
        self.history: list[dict] = []        # exactly as sent to the model, for Ollama's cache
        self.last_turn = 0.0
        self.forecast = Forecast()
        self.backend = BACKEND
        self.client = None
        self._stops = 0                         # Stop presses so far
        self._one_at_a_time = asyncio.Lock()   # one model, one cache: questions take turns
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
        asyncio.create_task(self.forecast.run())

    def stop(self) -> None:
        """Stop the answer being written now (the Stop button)."""
        self._stops += 1

    async def report(self, question: str = "") -> str:
        history = await asyncio.to_thread(self.house.store.history, 24, 48)
        return describe(self.house.snapshot(), history, self.forecast, question)

    async def ask(self, text: str, on_sentence: OnSentence | None = None) -> str:
        """Answer the question. If on_sentence is given, each finished sentence is passed to it
        as soon as it exists, so speech can start before the whole answer is written."""
        text = text.strip()
        stops = self._stops            # a Stop pressed from now on ends this answer
        async with self._one_at_a_time:
            if self.backend == "ollama":
                return await self._ollama(text, on_sentence, lambda: self._stops != stops)
            reply = await self._claude(text) if self.backend == "claude" else self._builtin(text)
            reply = speakable(reply)
            if on_sentence:
                await on_sentence(reply)
            return reply

    def _conversation(self) -> list[dict]:
        """The turns so far, or none if the last one was a while ago or the talk got long."""
        quiet = time.monotonic() - self.last_turn > FORGET_AFTER_S
        long = sum(len(m["content"]) for m in self.history) > MAX_HISTORY_CHARS
        if quiet or long:
            self.history = []
        return self.history

    def _remember(self, user: dict, reply: str) -> None:
        self.history += [user, {"role": "assistant", "content": reply}]
        self.last_turn = time.monotonic()

    async def _user_message(self, text: str) -> dict:
        return {"role": "user", "content": f"House report: {await self.report(text)}\n\nQuestion: {text}"}

    # ---- Ollama ----

    async def _warm_up(self) -> None:
        """Load the model with the real settings and read the system prompt into the cache, so
        the first question is as quick as the rest."""
        body = {
            "model": OLLAMA_MODEL, "stream": False, "keep_alive": -1,
            "options": {**OLLAMA_LOAD_OPTIONS, "num_predict": 1},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Hello."}],
        }
        for _ in range(120):
            try:
                r = await self.http.post("/api/chat", json=body)
                if r.status_code == 200:
                    log.info("ollama model %s loaded and ready", OLLAMA_MODEL)
                    return
                log.warning("ollama not ready (%s): %s", r.status_code, r.text[:200])
            except httpx.HTTPError:
                pass                                   # ollama is still starting
            await asyncio.sleep(15)

    async def _ollama(self, text: str, on_sentence: OnSentence | None, stopped_by_user=lambda: False) -> str:
        user = await self._user_message(text)
        body = {
            "model": OLLAMA_MODEL,
            "stream": True,
            "keep_alive": -1,
            "options": {**OLLAMA_LOAD_OPTIONS, "num_predict": MAX_REPLY_TOKENS, "temperature": 0.5},
            "messages": [{"role": "system", "content": SYSTEM}, *self._conversation(), user],
        }
        t0 = time.monotonic()
        first = None
        stats: dict = {}
        raw = ""                         # the answer exactly as written, for the cache
        spoken: list[str] = []
        chunker = Chunker()
        stopped = False

        async def say(part: str) -> None:
            part = speakable(part)
            if part:
                spoken.append(part)
                if on_sentence:
                    await on_sentence(part)

        try:
            async with self.http.stream("POST", "/api/chat", json=body) as r:
                if r.status_code == 404:
                    return (f"The model {OLLAMA_MODEL} is not downloaded yet. On the server, run: "
                            f"sudo docker compose exec ollama ollama pull {OLLAMA_MODEL}")
                if r.status_code != 200:
                    log.error("ollama %s: %s", r.status_code, (await r.aread())[:300])
                    return "The language model returned an error."
                async for line in r.aiter_lines():
                    if stopped_by_user():
                        stopped = True               # leaving the block hangs up; Ollama stops
                        break
                    if not line:
                        continue
                    msg = json.loads(line)
                    if msg.get("done"):
                        stats = msg
                    piece = msg.get("message", {}).get("content", "")
                    if not piece:
                        continue
                    if first is None:
                        first = time.monotonic() - t0
                    raw += piece
                    for part in chunker.feed(piece):
                        await say(part)
        except httpx.ConnectError:
            return "The language model service is not running on the server."
        except httpx.TimeoutException:
            return "The language model took too long to answer."

        cut_short = stats.get("done_reason") == "length"
        if cut_short:
            # The limit landed mid-sentence: drop the half sentence and say so properly.
            chunker.rest()
            await say(CUT_SHORT)
        elif not stopped:
            await say(chunker.rest())
        self._log_timing(t0, first, stats)
        reply = " ".join(spoken)
        if not reply:
            return "I have no answer for that."
        # Remember the turn word for word: next time Ollama finds it already read.
        self._remember(user, raw if not (cut_short or stopped) else reply)
        return reply

    @staticmethod
    def _log_timing(t0: float, first: float | None, stats: dict) -> None:
        """One line per answer showing where the time went, for `docker compose logs brain`."""
        def secs(key):
            return stats.get(key, 0) / 1e9
        read_n, write_n = stats.get("prompt_eval_count", 0), stats.get("eval_count", 0)
        log.info(
            "answer timing: total %.1fs, first words after %.1fs | load %.1fs | read %d tokens of "
            "prompt in %.1fs (%.0f/s) | wrote %d tokens in %.1fs (%.1f/s)",
            time.monotonic() - t0, first or 0, secs("load_duration"),
            read_n, secs("prompt_eval_duration"), read_n / max(secs("prompt_eval_duration"), 1e-3),
            write_n, secs("eval_duration"), write_n / max(secs("eval_duration"), 1e-3))

    # ---- Claude ----

    async def _claude(self, text: str) -> str:
        import anthropic

        user = await self._user_message(text)
        try:
            response = await self.client.beta.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=16000,
                system=SYSTEM,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[*self._conversation(), user],
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
        self._remember(user, reply)
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
