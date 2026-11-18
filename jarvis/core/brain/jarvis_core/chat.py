"""Answers questions, typed or spoken, as quickly and accurately as the house can.

Every question goes through these steps, fastest first:
  1. instant answers: time, date, our weather and forecast, dinner, devices, sums and "say that
     again" come from the house's own data in milliseconds (quick.py);
  2. a recent answer to the same question is repeated (kept for 15 minutes);
  3. Claude with live web search, when an Anthropic API key is set: accurate on any question,
     searching the internet only when the answer could have changed, streamed sentence by
     sentence so speaking starts as soon as the first sentence exists;
  4. the local model (Ollama) when there is no key or no internet.

CHAT_BACKEND: auto (default: Claude when ANTHROPIC_API_KEY is set, otherwise Ollama),
claude, ollama, or builtin (canned answers only).

The local model is quick on a Raspberry Pi because of Ollama's prompt cache: every request
starts with exactly the text of the previous one (the same system prompt, then the
conversation so far, word for word), so the model only reads the new question.
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
from .report import COUNTRY, PLACE, TZ_NAME, Forecast, describe

log = logging.getLogger("jarvis.chat")

BACKEND = os.environ.get("CHAT_BACKEND", "auto").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
OLLAMA_THREADS = int(os.environ.get("OLLAMA_THREADS", "3"))
MAX_REPLY_TOKENS = int(os.environ.get("MAX_REPLY_TOKENS", "400"))
# Internet answers (Claude). Named ONLINE_* so they can't clash with other programs' CLAUDE_* settings.
CLAUDE_MODEL = os.environ.get("ONLINE_MODEL", "").strip() or "claude-opus-5-5"
CLAUDE_EFFORT = os.environ.get("ONLINE_EFFORT", "").strip() or "low"     # low thinks least: quickest
CLAUDE_FAST = os.environ.get("ONLINE_FAST_MODE", "0") == "1"             # fast mode: quicker, dearer
WEB_SEARCHES = int(os.environ.get("WEB_SEARCHES", "2") or 2)             # most searches per question
SEARCH_FILTERING = os.environ.get("SEARCH_FILTERING", "0") == "1"        # filter results with code first

FORGET_AFTER_S = 180          # a pause this long starts a new conversation
MAX_HISTORY_CHARS = 3500      # about 900 tokens; longer starts a new conversation
REMEMBER_ANSWERS_S = 900      # repeat an internet answer to the same question for 15 minutes

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

CLAUDE_SYSTEM = """You are J.A.R.V.I.S., the voice assistant for one household. Your answers \
are read aloud by a speaker and shown on a small screen.

Answer in one or two short spoken sentences unless asked for more, with the answer first. Use \
plain words only: no markdown, lists, emoji, web addresses or citation marks.

You have a web search tool. Use it when the answer depends on facts that may have changed or \
that you are not sure of, such as news, sport, prices, weather elsewhere, opening times, \
people's current roles or recent releases. Don't search for settled knowledge, sums, or \
anything the house report already says. One search is usually enough. Summarise what you find \
in your own words.

Each question comes with a house report: the date and time, our own weather station, the local \
forecast, dinner, and which devices are online. Use it for questions about the house, the local \
weather or the time, and ignore it otherwise. You can't control anything in the house yet; say \
so if asked."""

CUT_SHORT = "I'll stop there. Say go on if you want more."

OnSentence = Callable[[str], Awaitable[None]]
OnStatus = Callable[[str], Awaitable[None]]

_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_MARKDOWN = re.compile(r"^\s*(?:[-*•]|#+)\s+|[*_`#]+", re.M)
_LINKS = re.compile(r"\(?https?://\S+\)?")


def speakable(text: str) -> str:
    """Text as it should be spoken and shown: no markdown symbols, no web addresses."""
    return " ".join(_MARKDOWN.sub("", _LINKS.sub("", text)).split())


# Models whose web search can run a small program over the results first and read only the
# relevant parts ("dynamic filtering").
_FILTERING_MODELS = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-fable",
                     "claude-mythos", "claude-sonnet-5", "claude-sonnet-4-6")
# Models that can hand a declined question to a backup model on Anthropic's side.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-2", "claude-fable-5-1",
                    "claude-mythos-5-2", "claude-sonnet-5-5"}
# Models with fast mode that needs no sign-up.
_FAST_MODELS = {"claude-opus-5-5", "claude-fable-5-2", "claude-mythos-5-2"}


def _search_tool(model: str) -> dict:
    """Claude's web search, near our location. Normally Claude reads the results itself, the
    quickest way to a short answer. With SEARCH_FILTERING=1 it first writes and runs a small
    program that keeps only the relevant parts: fewer tokens on long searches, one more step."""
    if SEARCH_FILTERING and model.startswith(_FILTERING_MODELS):
        tool = {"type": "web_search_20260209", "name": "web_search"}
    else:
        tool = {"type": "web_search_20250305", "name": "web_search"}
    tool["max_uses"] = WEB_SEARCHES
    where = {k: v for k, v in (("city", PLACE), ("country", COUNTRY), ("timezone", TZ_NAME)) if v}
    if where:
        tool["user_location"] = {"type": "approximate", **where}
    return tool


def _has_fallbacks(model: str) -> bool:
    return model in _FALLBACK_MODELS


def _problem(e: Exception) -> str:
    """What went wrong with an internet answer, in words that make sense spoken aloud."""
    import anthropic

    said = str(getattr(e, "message", e)).lower()
    if isinstance(e, anthropic.AuthenticationError):
        return "My API key was rejected"
    if "credit balance" in said:
        return "The API account is out of credit"
    if "web search" in said and isinstance(e, (anthropic.BadRequestError, anthropic.PermissionDeniedError)):
        return "Web search is switched off for this API account"
    if isinstance(e, anthropic.NotFoundError):
        return "The internet model in my settings doesn't exist"
    if isinstance(e, anthropic.RateLimitError):
        return "I've hit the API account's rate limit"
    if isinstance(e, (anthropic.BadRequestError, anthropic.PermissionDeniedError)):
        return "The internet service turned down my request"
    if isinstance(e, anthropic.InternalServerError):
        return "The internet service is busy"
    return "I can't reach the internet right now"


def _sources(message) -> list[dict]:
    """The web pages an answer was drawn from: title and address, each once."""
    seen, out = set(), []
    for block in getattr(message, "content", None) or []:
        for c in getattr(block, "citations", None) or []:
            url = getattr(c, "url", None)
            if url and url not in seen:
                seen.add(url)
                out.append({"title": getattr(c, "title", None) or url, "url": url})
    return out[:5]


def _cacheable(q: str) -> bool:
    """Only questions that mean the same thing on their own, not follow-ups like "why"."""
    words = q.split()
    follow_up = {"it", "its", "that", "this", "they", "them", "he", "she", "him", "her", "those",
                 "these", "there", "again", "more", "else"}
    return (len(words) >= 3 and not q.startswith(("and ", "so ", "but ", "why", "what about", "how about"))
            and not follow_up & set(words))


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
        self.last_answer = ""
        self.last_sources: list[dict] = []     # web pages the last answer came from
        self.answers: dict[str, tuple[float, str, list]] = {}   # recent internet answers
        self.forecast = Forecast()
        self.client = None
        self._warmed = -1e9                     # when the connection to Anthropic was last used
        self._stops = 0                         # Stop presses so far
        self._one_at_a_time = asyncio.Lock()   # one model, one cache: questions take turns
        self.http = httpx.AsyncClient(base_url=OLLAMA_URL, timeout=httpx.Timeout(240, connect=5))
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.backend = {"auto": "claude" if has_key else "ollama"}.get(BACKEND, BACKEND)
        if self.backend == "claude" and not has_key:
            log.warning("CHAT_BACKEND=claude but ANTHROPIC_API_KEY is empty; using the local model")
            self.backend = "ollama"
        if self.backend == "claude":
            import anthropic
            import httpx2           # the SDK's own copy of httpx

            self.client = anthropic.AsyncAnthropic(
                timeout=anthropic.Timeout(30.0, connect=5.0), max_retries=1,
                # Keep the secure connection open between questions (the SDK closes it after
                # 5 idle seconds), so a question doesn't first wait for a new one.
                http_client=anthropic.DefaultAsyncHttpxClient(
                    limits=httpx2.Limits(max_connections=10, max_keepalive_connections=2, keepalive_expiry=300)))
            if CLAUDE_FAST and CLAUDE_MODEL not in _FAST_MODELS:
                log.warning("ONLINE_FAST_MODE=1 does nothing on %s; fast mode needs one of %s",
                            CLAUDE_MODEL, ", ".join(sorted(_FAST_MODELS)))
        log.info("chat backend: %s", self.backend if self.backend != "claude" else f"claude ({CLAUDE_MODEL})")

    async def start(self) -> None:
        """Call once the event loop is running."""
        if self.backend in ("ollama", "claude"):        # with Claude, the local model stands by
            asyncio.create_task(self._warm_up())
        asyncio.create_task(self.forecast.run())

    def stop(self) -> None:
        """Stop the answer being written now (the Stop button)."""
        self._stops += 1

    def get_ready(self) -> None:
        """Someone has started speaking or typing a question: open the connection to Anthropic
        now, so the answer doesn't wait for it. Listing one model is free."""
        if self.backend != "claude" or time.monotonic() - self._warmed < 60:
            return
        self._warmed = time.monotonic()

        async def connect() -> None:
            try:
                await self.client.models.list(limit=1)
            except Exception as e:
                log.info("could not open the connection to Anthropic ahead of time (%s)", e.__class__.__name__)

        asyncio.create_task(connect())

    async def report(self, question: str = "") -> str:
        history = await asyncio.to_thread(self.house.store.history, 24, 48)
        return describe(self.house.snapshot(), history, self.forecast, question)

    async def ask(self, text: str, on_sentence: OnSentence | None = None,
                  on_status: OnStatus | None = None) -> str:
        """Answer the question. If on_sentence is given, each finished sentence is passed to it
        as soon as it exists, so speech can start before the whole answer is written. on_status
        hears "searching" when the answer needs the internet. Afterwards, last_sources lists the
        web pages the answer came from."""
        text = text.strip()
        stops = self._stops            # a Stop pressed from now on ends this answer
        stopped_by_user = lambda: self._stops != stops

        instant = quick.answer(text, self.house.snapshot(), self.forecast, self.last_answer)
        sources: list[dict] = []
        if instant is None:
            hit = self._recent_answer(text)
            if hit:
                instant, sources = (hit[0], "recent"), hit[1]
        if instant:
            reply, kind = instant
            log.info("instant answer (%s)", kind)
            if on_sentence:
                await on_sentence(reply)
            if kind != "repeat":
                self.last_sources = sources
                self._remember({"role": "user", "content": f"Question: {text}"}, reply)
            return reply

        async with self._one_at_a_time:
            self.last_sources = []
            if self.backend == "claude":
                reply = await self._claude(text, on_sentence, on_status, stopped_by_user)
            elif self.backend == "ollama":
                reply = await self._ollama(text, on_sentence, stopped_by_user)
            else:
                reply = speakable(self._builtin(text))
                if on_sentence:
                    await on_sentence(reply)
        self.last_answer = reply
        return reply

    def _recent_answer(self, text: str) -> tuple[str, list] | None:
        q = quick.normalise(text)
        hit = self.answers.get(q)
        if hit and time.monotonic() - hit[0] < REMEMBER_ANSWERS_S:
            return hit[1], hit[2]
        return None

    def _keep_answer(self, text: str, reply: str, sources: list) -> None:
        q = quick.normalise(text)
        if _cacheable(q):
            if len(self.answers) > 200:
                self.answers.clear()
            self.answers[q] = (time.monotonic(), reply, sources)

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

    def _claude_params(self, messages: list[dict]) -> dict:
        params = {
            "model": CLAUDE_MODEL,
            "max_tokens": 8000,
            "system": CLAUDE_SYSTEM,
            "output_config": {"effort": CLAUDE_EFFORT},
            "tools": [_search_tool(CLAUDE_MODEL)],
            "messages": messages,
        }
        if _has_fallbacks(CLAUDE_MODEL):
            # If the model declines a question, Anthropic retries it on a backup model.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        if CLAUDE_FAST:
            params["speed"] = "fast"
        return params

    async def _claude(self, text: str, on_sentence: OnSentence | None, on_status: OnStatus | None,
                      stopped_by_user) -> str:
        import anthropic

        user = await self._user_message(text)
        messages = [*self._conversation(), user]
        params = self._claude_params(messages)
        t0 = time.monotonic()
        first = None
        searching = False
        spoken: list[str] = []
        chunker = Chunker()
        stopped = False
        finals = []

        async def say(part: str) -> None:
            part = speakable(part)
            if part:
                spoken.append(part)
                if on_sentence:
                    await on_sentence(part)

        while True:
            try:
                params["messages"] = messages
                for _ in range(2):                # a paused search turn is resumed once
                    async with self.client.beta.messages.stream(**params) as stream:
                        async for event in stream:
                            if stopped_by_user():
                                stopped = True    # leaving the block hangs up; Claude stops
                                break
                            if event.type == "content_block_start" and event.content_block.type == "server_tool_use":
                                if not searching:
                                    searching = True
                                    if on_status:
                                        await on_status("searching")
                            elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                                if first is None:
                                    first = time.monotonic() - t0
                                for part in chunker.feed(event.delta.text):
                                    await say(part)
                        if stopped:
                            break
                        finals.append(await stream.get_final_message())
                    # A paused turn is sent back to carry on, except after a switch to the backup
                    # model, which can't take everything from before the switch (very rare).
                    if (finals[-1].stop_reason != "pause_turn"
                            or any(b.type == "fallback" for b in finals[-1].content)):
                        break
                    params["messages"] = [*messages, {"role": "assistant", "content": finals[-1].content}]
                break
            except anthropic.APIError as e:
                busy = isinstance(e, (anthropic.RateLimitError, anthropic.OverloadedError))
                if busy and params.get("speed") and not spoken and not finals:
                    log.info("fast mode is busy; answering at standard speed")
                    params.pop("speed")
                    continue
                log.warning("Claude unavailable (%s: %s)", e.__class__.__name__, getattr(e, "message", e))
                if spoken:
                    return " ".join(spoken)       # half an answer already said: leave it there
                return await self._from_memory(text, _problem(e), on_sentence, stopped_by_user)
        self._warmed = time.monotonic()           # the connection is open now

        final = finals[-1] if finals else None
        reason = None if stopped else getattr(final, "stop_reason", None)
        refused, cut_short = reason == "refusal", reason in ("max_tokens", "pause_turn")
        if refused:
            # Declined, and no backup model took it. Words already said aren't a whole answer,
            # so the conversation keeps only the notice.
            notice = "I can't finish that answer." if spoken else "I can't help with that one."
            await say(notice)
            spoken = [notice]
        elif cut_short:
            chunker.rest()
            await say(CUT_SHORT)
        elif not stopped:
            await say(chunker.rest())
        sources = [s for f in finals for s in _sources(f)]
        self.last_sources = list({s["url"]: s for s in sources}.values())[:5]
        searches = sum(getattr(getattr(getattr(f, "usage", None), "server_tool_use", None),
                               "web_search_requests", 0) or 0 for f in finals)
        log.info("answer timing (claude %s%s): total %.1fs, first words after %.1fs | %d web searches | "
                 "%d tokens read, %d written", getattr(final, "model", CLAUDE_MODEL),
                 ", fast" if params.get("speed") else "", time.monotonic() - t0, first or 0, searches,
                 sum(f.usage.input_tokens for f in finals), sum(f.usage.output_tokens for f in finals))
        reply = " ".join(spoken) or "I have no answer for that."
        self._remember(user, reply)
        if not (stopped or refused or cut_short):
            self._keep_answer(text, reply, self.last_sources)
        return reply

    async def _from_memory(self, text: str, reason: str, on_sentence: OnSentence | None, stopped_by_user) -> str:
        """No internet: say so, then answer with the local model."""
        notice = f"{reason}, so this is from memory."
        if on_sentence:
            await on_sentence(notice)
        reply = await self._ollama(text, on_sentence, stopped_by_user)
        return f"{notice} {reply}"

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
