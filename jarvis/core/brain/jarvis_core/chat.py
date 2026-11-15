"""Answers typed questions. Uses Claude when an API key is set, simple built-in replies otherwise."""
import json
import logging
import os
from collections import deque

import anthropic

log = logging.getLogger("jarvis.chat")

MODEL = "claude-opus-5-5"

SYSTEM = """You are J.A.R.V.I.S., the assistant for one household. Your replies are shown on a \
small touchscreen and read aloud, so answer in one to three plain spoken sentences with no \
markdown, lists or emoji. Be dry, calm and precise.

Each user message starts with a <house_state> block holding live readings from the house: the \
outdoor weather station, which devices are online, and whether dinner has been called. Use it \
when the question is about the house. A reading marked stale is old and should be described as \
such. You cannot control anything in the house; if asked to, say so."""


class Chat:
    def __init__(self, house):
        self.house = house
        self.client = anthropic.AsyncAnthropic() if os.environ.get("ANTHROPIC_API_KEY") else None
        self.history: deque[dict] = deque(maxlen=12)   # plain-text turns only

    async def ask(self, text: str) -> str:
        if not self.client:
            return self._builtin(text)
        state = json.dumps(self.house.snapshot(), separators=(",", ":"))
        messages = [*self.history, {"role": "user", "content": f"<house_state>{state}</house_state>\n\n{text}"}]
        try:
            response = await self.client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                output_config={"effort": "low"},
                # If the model declines a request, the API retries it on a fallback model.
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
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

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
        return ("Without an API key I can only answer about the weather and dinner. "
                "Add ANTHROPIC_API_KEY to the server's .env file for anything else.")
