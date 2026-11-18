"""Answers questions, typed or spoken, as quickly and accurately as the house can.

Every question goes through these steps, fastest first:
  1. instant answers: the time, the date, our weather and forecast, dinner, devices, sums and
     "say that again" come from the house's own data in milliseconds (quick.py);
  2. the same question again within 15 minutes gets the same answer, instantly;
  3. the local language model (Ollama), streamed in pieces, so speaking starts as soon as the
     first words exist.

The local model is quick on a Raspberry Pi because it hardly ever reads anything twice. Ollama
keeps what it read last, and every request starts with exactly that text: the same
instructions, then the conversation so far, word for word. On top of that, while someone is
still speaking or typing, the model already reads everything that comes before their words
(the conversation and the house report), so when the question arrives it only reads the
question itself.

CHAT_BACKEND: ollama (default), or builtin (canned answers about the weather and dinner only).
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Awaitable, Callable

import httpx

from . import quick
from .report import Forecast, base, clock_text, describe, details, topics

log = logging.getLogger("jarvis.chat")

BACKEND = os.environ.get("CHAT_BACKEND", "ollama").strip().lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_THREADS = int(os.environ.get("OLLAMA_THREADS", "3"))
MAX_REPLY_TOKENS = int(os.environ.get("MAX_REPLY_TOKENS", "400"))

FORGET_AFTER_S = 180          # a pause this long starts a new conversation
MAX_HISTORY_CHARS = 3500      # about 900 tokens; longer starts a new conversation
REMEMBER_ANSWERS_S = 900      # the same question again within 15 minutes gets the same answer
HOLD_CLOCK_S = 60             # a question this soon after reading ahead keeps the time read ahead

# Settings Ollama loads the model with. They must be identical on every request, or Ollama
# reloads the model and throws its cache away. One core is left for the camera and speech.
OLLAMA_LOAD_OPTIONS = {"num_ctx": 2048, "num_thread": OLLAMA_THREADS}
# For answers: a low temperature makes the model give its likeliest answer, not a creative one.
ANSWER_OPTIONS = {**OLLAMA_LOAD_OPTIONS, "num_predict": MAX_REPLY_TOKENS, "temperature": 0.3}

# Read once when the model loads and kept in Ollama's cache, so its length costs nothing per
# question. Small models copy examples far better than they follow rules.
SYSTEM = """You are J.A.R.V.I.S., the assistant for one household. Your replies are read aloud \
by a speaker and shown on a small screen.

Answer in one or two short spoken sentences, with the answer itself first, and only give more \
detail when asked for it. No markdown, no lists, no emoji. Be dry, calm and precise. If you are \
not sure of a fact, say so instead of guessing. Your knowledge stops at your training, so for \
things that change, such as who holds an office, say what you knew and that it may have changed. \
If asked to control something in the house, say you cannot do that yet.

Each question comes with a house report: the date and time, the temperature from our own \
weather station, and more about the weather, dinner or the devices when the question is about \
them. Use it for questions about the house, the weather or the time, and ignore it otherwise. \
Never read the report out; answer only what was asked.

Examples of good answers:
Q: Who wrote Pride and Prejudice? A: Jane Austen, published in 1813.
Q: How far away is the Moon? A: About 384,000 kilometres, on average.
Q: Who won the 2031 World Cup? A: I don't know; that is after my training."""

CUT_SHORT = "I'll stop there. Say go on if you want more."

OnSentence = Callable[[str], Awaitable[None]]

_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_MARKDOWN = re.compile(r"^\s*(?:[-*•]|#+)\s+|[*_`#]+", re.M)
_LINKS = re.compile(r"\(?https?://\S+\)?")
# Answers to questions with these words can be wrong a few minutes later, so they aren't repeated.
_CHANGES = re.compile(r"\b(time|now|minutes?|hours?|clock|tonight|today|tomorrow|until|left|late|early)\b")


def speakable(text: str) -> str:
    """Text as it should be spoken and shown: no markdown symbols, no web addresses."""
    return " ".join(_MARKDOWN.sub("", _LINKS.sub("", text)).split())


def _cacheable(q: str) -> bool:
    """Questions that mean the same thing on their own (not follow-ups like "why") and whose
    answer stays right for a while (nothing about the time, the weather or the house)."""
    words = q.split()
    follow_up = {"it", "its", "that", "this", "they", "them", "he", "she", "him", "her", "those",
                 "these", "there", "again", "more", "else"}
    return (len(words) >= 3 and not q.startswith(("and ", "so ", "but ", "why", "what about", "how about"))
            and not follow_up & set(words) and not _CHANGES.search(q) and not topics(q))


def _user_content(report: str, question: str | None) -> str:
    """The message the model gets. Read ahead without the question (None), it is the start of
    the message the question arrives in later, word for word."""
    return f"House report: {report}\n\nQuestion:" + (f" {question}" if question is not None else "")


class Chunker:
    """Cuts streamed text into pieces worth speaking: whole sentences; the first words up to a
    comma, so speaking starts sooner; and the start of a very long sentence at a comma."""

    FIRST = 30      # the first piece may end at a comma once it is at least this long
    LONG = 160

    def __init__(self):
        self.buf = ""
        self.started = False

    def feed(self, piece: str) -> list[str]:
        self.buf += piece
        *parts, self.buf = _BREAK.split(self.buf)
        if not self.started and not parts:
            cut = self.buf.find(", ", self.FIRST)
            if cut != -1:
                parts.append(self.buf[:cut + 1])
                self.buf = self.buf[cut + 2:]
        if len(self.buf) > self.LONG:
            cut = self.buf.rfind(", ", 0, self.LONG)
            if cut > 40:
                parts.append(self.buf[:cut + 1])
                self.buf = self.buf[cut + 2:]
        parts = [p for p in parts if p.strip()]
        if parts:
            self.started = True
        return parts

    def rest(self) -> str:
        rest, self.buf = self.buf, ""
        return rest


class Chat:
    def __init__(self, house):
        self.house = house
        self.history: list[dict] = []        # exactly as sent to the model, for Ollama's cache
        self.last_turn = 0.0
        self.last_answer = ""
        self.answers: dict[str, tuple[float, str]] = {}   # recent answers, by question
        self.forecast = Forecast()
        self._stops = 0                         # Stop presses so far
        self._one_at_a_time = asyncio.Lock()   # one model, one cache: questions take turns
        self._held_clock = (-1e9, "")          # the time read ahead, for the coming question
        self._read_ahead_for = ""              # the request Ollama read ahead last (it still holds it)
        self.http = httpx.AsyncClient(base_url=OLLAMA_URL, timeout=httpx.Timeout(240, connect=5))
        self.backend = BACKEND if BACKEND in ("ollama", "builtin") else "ollama"
        if self.backend != BACKEND:
            log.warning("CHAT_BACKEND=%s is not used any more; answering with the local model", BACKEND)
        log.info("chat backend: %s", f"ollama ({OLLAMA_MODEL})" if self.backend == "ollama" else self.backend)

    async def start(self) -> None:
        """Call once the event loop is running."""
        if self.backend == "ollama":
            asyncio.create_task(self._warm_up())
        asyncio.create_task(self.forecast.run())

    def stop(self) -> None:
        """Stop the answer being written now (the Stop button)."""
        self._stops += 1

    def get_ready(self) -> None:
        """Someone has started asking (the wake word, the Talk button, or a click in the
        question box): read ahead while they speak or type."""
        if self.backend == "ollama" and not self._one_at_a_time.locked():
            asyncio.create_task(self._read_ahead())

    async def report(self, question: str = "") -> str:
        history = await asyncio.to_thread(self.house.store.history, 24, 48)
        return describe(self.house.snapshot(), history, self.forecast, question)

    async def ask(self, text: str, on_sentence: OnSentence | None = None) -> str:
        """Answer the question. If on_sentence is given, each piece of the answer is passed to it
        as soon as it exists, so speech can start before the whole answer is written."""
        text = text.strip()
        stops = self._stops            # a Stop pressed from now on ends this answer
        stopped_by_user = lambda: self._stops != stops

        instant = quick.answer(text, self.house.snapshot(), self.forecast, self.last_answer)
        if instant is None:
            again = self._recent_answer(text)
            if again:
                instant = (again, "recent")
        if instant:
            reply, kind = instant
            log.info("instant answer (%s)", kind)
            if on_sentence:
                await on_sentence(reply)
            if kind != "repeat":
                self._remember({"role": "user", "content": f"Question: {text}"}, reply)
            return reply

        async with self._one_at_a_time:
            if self.backend == "ollama":
                reply = await self._ollama(text, on_sentence, stopped_by_user)
            else:
                reply = speakable(self._builtin(text))
                if on_sentence:
                    await on_sentence(reply)
        self.last_answer = reply
        return reply

    def _recent_answer(self, text: str) -> str | None:
        hit = self.answers.get(quick.normalise(text))
        if hit and time.monotonic() - hit[0] < REMEMBER_ANSWERS_S:
            return hit[1]
        return None

    def _keep_answer(self, text: str, reply: str) -> None:
        q = quick.normalise(text)
        if _cacheable(q):
            if len(self.answers) > 200:
                self.answers.clear()
            self.answers[q] = (time.monotonic(), reply)

    def _conversation(self) -> list[dict]:
        """The turns so far, or none if the last one was a while ago or the talk got long."""
        quiet = time.monotonic() - self.last_turn > FORGET_AFTER_S
        long = sum(len(m["content"]) for m in self.history) > MAX_HISTORY_CHARS
        if quiet or long:
            self.history = []
        return self.history

    def _remember(self, user: dict, reply: str) -> None:
        self._conversation()                     # forget an old conversation first
        self.history += [user, {"role": "assistant", "content": reply}]
        self.last_turn = time.monotonic()
        self.last_answer = speakable(reply)

    async def _house_report(self, question: str | None) -> str:
        """The report for a question, or with question None, the part that is the same for any
        question, for reading ahead. A question soon after keeps the time that was read ahead,
        so its message starts exactly like the one read ahead."""
        now = time.monotonic()
        if question is None:
            self._held_clock = (now, clock_text())
            clock = self._held_clock[1]
        elif now - self._held_clock[0] < HOLD_CLOCK_S:
            clock = self._held_clock[1]
        else:
            clock = clock_text()
        snapshot = self.house.snapshot()
        report = base(snapshot, clock)
        if question is not None:
            weather = "weather" in topics(question)
            history = await asyncio.to_thread(self.house.store.history, 24, 48) if weather else []
            extra = details(snapshot, history, self.forecast, question)
            if extra:
                report += " " + extra
        return report

    # ---- Ollama ----

    async def _warm_up(self) -> None:
        """Load the model with the real settings and read the instructions into the cache, so
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

    async def _read_ahead(self) -> None:
        """Have the model read everything that will come before the question: the instructions,
        the conversation so far and the house report. Ollama keeps what it read, so the question
        then only adds its own few words."""
        async with self._one_at_a_time:
            history = self._conversation()
            if history:
                self.last_turn = time.monotonic()      # they're asking again: the conversation goes on
            user = {"role": "user", "content": _user_content(await self._house_report(None), None)}
            messages = [{"role": "system", "content": SYSTEM}, *history, user]
            key = json.dumps(messages)
            if key == self._read_ahead_for:
                return                                 # read exactly this last time; Ollama still has it
            body = {"model": OLLAMA_MODEL, "stream": False, "keep_alive": -1,
                    "options": {**OLLAMA_LOAD_OPTIONS, "num_predict": 1}, "messages": messages}
            t0 = time.monotonic()
            try:
                r = await self.http.post("/api/chat", json=body)
                stats = r.json() if r.status_code == 200 else {}
            except (httpx.HTTPError, ValueError) as e:
                log.info("could not read ahead (%s)", e.__class__.__name__)
                return
            if r.status_code == 200:
                self._read_ahead_for = key
                # Ollama counts the whole prompt, including what it already had: the time is what matters.
                log.info("read ahead in %.1fs (prompt %d tokens): ready for the question",
                         time.monotonic() - t0, stats.get("prompt_eval_count", 0))

    async def _ollama(self, text: str, on_sentence: OnSentence | None, stopped_by_user=lambda: False) -> str:
        user = {"role": "user", "content": _user_content(await self._house_report(text), text)}
        body = {
            "model": OLLAMA_MODEL,
            "stream": True,
            "keep_alive": -1,
            "options": ANSWER_OPTIONS,
            "messages": [{"role": "system", "content": SYSTEM}, *self._conversation(), user],
        }
        self._read_ahead_for = ""        # from now on Ollama holds this request instead
        t0 = time.monotonic()
        first = said = None
        stats: dict = {}
        raw = ""                         # the answer exactly as written, for the cache
        spoken: list[str] = []
        chunker = Chunker()
        stopped = False

        async def say(part: str) -> None:
            nonlocal said
            part = speakable(part)
            if part:
                if said is None:
                    said = time.monotonic() - t0
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
        self._log_timing(t0, first, said, stats)
        reply = " ".join(spoken)
        if not reply:
            return "I have no answer for that."
        # Remember the turn word for word: next time Ollama finds it already read.
        self._remember(user, raw if not (cut_short or stopped) else reply)
        if not (cut_short or stopped):
            self._keep_answer(text, reply)
        return reply

    @staticmethod
    def _log_timing(t0: float, first: float | None, said: float | None, stats: dict) -> None:
        """One line per answer showing where the time went, for `docker compose logs brain`. The
        prompt count includes what was already read ahead; the read time is only the new part."""
        def secs(key):
            return stats.get(key, 0) / 1e9
        read_n, write_n = stats.get("prompt_eval_count", 0), stats.get("eval_count", 0)
        log.info(
            "answer timing: total %.1fs, first words written after %.1fs, first words to say after %.1fs | "
            "load %.1fs | prompt %d tokens, read in %.1fs | wrote %d tokens in %.1fs (%.1f/s)",
            time.monotonic() - t0, first or 0, said or 0, secs("load_duration"),
            read_n, secs("prompt_eval_duration"),
            write_n, secs("eval_duration"), write_n / max(secs("eval_duration"), 1e-3))

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
