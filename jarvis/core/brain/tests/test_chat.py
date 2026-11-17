import asyncio
import json

import httpx

from jarvis_core import chat as chat_mod
from jarvis_core.chat import CUT_SHORT, Chat, Chunker, speakable


def test_chunker_splits_sentences_and_newlines():
    c = Chunker()
    out = []
    for piece in ["It is 8.4 degre", "es outside. Light ", "rain later!\n- bring", " a coat"]:
        out += c.feed(piece)
    assert out == ["It is 8.4 degrees outside.", "Light rain later!"]
    assert c.rest() == "- bring a coat"


def test_chunker_speaks_the_start_of_a_very_long_sentence():
    c = Chunker()
    long = "The Eiffel Tower, which was finished in 1889 for the World's Fair, " * 4
    parts = c.feed(long)
    assert parts and parts[0].endswith(",") and len(parts[0]) <= Chunker.LONG + 1


def test_speakable_removes_markdown():
    assert speakable("**Paris** is the `capital`.\n- one\n# Title") == "Paris is the capital. one Title"


class FakeStore:
    def history(self, hours, max_points):
        return []


class FakeHouse:
    store = FakeStore()

    def snapshot(self):
        return {"weather": None, "dinner": {"state": "idle"}, "nodes": {}, "cameras": {}}


def ollama_stub(replies, seen):
    """An Ollama that streams the given replies one word at a time and records each request."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        text, reason = replies.pop(0)
        lines = [json.dumps({"message": {"content": w + " "}, "done": False}) for w in text.split()]
        lines.append(json.dumps({"message": {"content": ""}, "done": True, "done_reason": reason,
                                 "prompt_eval_count": 10, "prompt_eval_duration": 10**9,
                                 "eval_count": 5, "eval_duration": 10**9}))
        return httpx.Response(200, content="\n".join(lines).encode())
    return httpx.MockTransport(handler)


def make_chat(replies, seen):
    c = Chat.__new__(Chat)
    Chat.__init__(c, FakeHouse())
    c.backend = "ollama"
    c.http = httpx.AsyncClient(base_url="http://ollama", transport=ollama_stub(replies, seen))
    return c


async def test_conversation_is_resent_word_for_word_for_the_cache():
    seen = []
    c = make_chat([("Hello there. How can I help?", "stop"), ("It is Tuesday.", "stop")], seen)
    spoken = []

    async def say(s):
        spoken.append(s)

    assert await c.ask("hello", say) == "Hello there. How can I help?"
    assert spoken == ["Hello there.", "How can I help?"]
    await c.ask("what day is it", say)
    first, second = seen
    # the second request starts with exactly what the first one sent, then the reply as written
    assert second["messages"][:2] == first["messages"]
    assert second["messages"][2]["role"] == "assistant"
    assert second["messages"][2]["content"].startswith("Hello there.")
    # load settings identical every time, or Ollama reloads the model
    assert first["options"]["num_ctx"] == second["options"]["num_ctx"]
    assert first["options"]["num_thread"] == second["options"]["num_thread"]


async def test_cut_off_answer_ends_on_a_full_sentence():
    seen = []
    c = make_chat([("Paris is old. It was founded by the Parisii in", "length")], seen)
    spoken = []

    async def say(s):
        spoken.append(s)

    reply = await c.ask("tell me about paris", say)
    assert spoken == ["Paris is old.", CUT_SHORT]
    assert reply == f"Paris is old. {CUT_SHORT}"


async def test_quiet_spell_starts_a_new_conversation(monkeypatch):
    seen = []
    c = make_chat([("One.", "stop"), ("Two.", "stop")], seen)
    await c.ask("first")
    c.last_turn -= chat_mod.FORGET_AFTER_S + 1
    await c.ask("second")
    assert [m["role"] for m in seen[1]["messages"]] == ["system", "user"]


async def test_stop_ends_the_answer_early():
    seen = []
    c = make_chat([("One. Two. Three. Four.", "stop")], seen)
    spoken = []

    async def say(s):
        spoken.append(s)
        if len(spoken) == 1:
            c.stop()

    await c.ask("count", say)
    assert spoken == ["One."]
