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
    """An Ollama that streams the given replies one word at a time and records each request.
    Requests that don't stream (loading, reading ahead) get one reply and use up no answer."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("stream") is False:
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "."}, "done": True,
                                             "prompt_eval_count": 42})
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
    c = make_chat([("Hello there. How can I help?", "stop"), ("Lima is the capital.", "stop")], seen)
    spoken = []

    async def say(s):
        spoken.append(s)

    assert await c.ask("hello", say) == "Hello there. How can I help?"
    assert spoken == ["Hello there.", "How can I help?"]
    await c.ask("what is the capital of peru", say)
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


def test_chunker_starts_talking_at_the_first_comma():
    c = Chunker()
    out = c.feed("The capital of Australia is Canberra, which was chosen as a compromise")
    assert out == ["The capital of Australia is Canberra,"]
    assert c.feed(" between Sydney and Melbourne. It is small.") == ["which was chosen as a compromise between Sydney and Melbourne."]
    short = Chunker()
    assert short.feed("Yes, it is, mostly") == []            # too short to be worth saying alone


def model_requests(seen):
    return [r for r in seen if r.get("stream")]


async def test_reading_ahead_leaves_only_the_question_to_read():
    seen = []
    c = make_chat([("Hello there.", "stop"), ("Lima is the capital.", "stop")], seen)
    await c.ask("hello")
    c.get_ready()                                         # someone says "Hey Jarvis" again
    await asyncio.sleep(0.05)
    ahead = seen[-1]
    assert ahead["stream"] is False and ahead["options"]["num_predict"] == 1
    assert ahead["messages"][-1]["content"].endswith("\n\nQuestion:")
    await c.ask("what is the capital of peru")
    real = model_requests(seen)[-1]
    # everything before the question is word for word what was read ahead
    assert real["messages"][:-1] == ahead["messages"][:-1]
    assert real["messages"][-1]["content"] == ahead["messages"][-1]["content"] + " what is the capital of peru"
    # same load settings, so Ollama keeps the model and what it read
    assert {k: ahead["options"][k] for k in ("num_ctx", "num_thread")} == \
           {k: real["options"][k] for k in ("num_ctx", "num_thread")}


async def test_reading_ahead_is_not_repeated_and_waits_for_a_running_answer():
    seen = []
    c = make_chat([("One.", "stop")], seen)
    c.get_ready()
    await asyncio.sleep(0.05)
    c.get_ready()                                         # nothing new since: nothing to read
    await asyncio.sleep(0.05)
    assert len([r for r in seen if r.get("stream") is False]) == 1
    async with c._one_at_a_time:                          # an answer is being written
        c.get_ready()
        await asyncio.sleep(0.05)
    assert len([r for r in seen if r.get("stream") is False]) == 1


async def test_same_question_again_is_instant_unless_it_depends_on_the_time():
    seen = []
    c = make_chat([("Canberra.", "stop"), ("About ten minutes.", "stop"), ("About nine minutes.", "stop")], seen)
    assert await c.ask("what is the capital of australia") == "Canberra."
    assert await c.ask("What is the capital of Australia?") == "Canberra." and len(model_requests(seen)) == 1
    await c.ask("how long until the bus comes")
    assert await c.ask("how long until the bus comes") == "About nine minutes."
    assert len(model_requests(seen)) == 3


async def test_instant_answers_never_reach_the_model():
    seen = []
    c = make_chat([], seen)
    assert (await c.ask("what's 12 times 12")) == "12 times 12 is 144."
    assert (await c.ask("say that again")) == "12 times 12 is 144."
    assert model_requests(seen) == []


async def test_answers_are_focused_and_load_settings_stay_fixed():
    seen = []
    c = make_chat([("Jane Austen.", "stop")], seen)
    await c.ask("who wrote pride and prejudice")
    options = model_requests(seen)[0]["options"]
    assert options["temperature"] <= 0.3 and options["num_ctx"] == chat_mod.OLLAMA_LOAD_OPTIONS["num_ctx"]
