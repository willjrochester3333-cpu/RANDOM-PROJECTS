"""The Claude path, against a stand-in that streams Claude's real event format."""
import asyncio
import json

import anthropic
import httpx
import httpx2          # the Anthropic SDK brings its own copy of httpx

from jarvis_core import chat as chat_mod
from jarvis_core.chat import Chat
from test_chat import FakeHouse, ollama_stub


def sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def message(blocks: list[list[dict]], stop_reason: str = "end_turn") -> bytes:
    events = [{"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 50, "output_tokens": 1}}}]
    for i, block in enumerate(blocks):
        for e in block:
            events.append({**e, "index": i})
    events += [{"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 20}},
               {"type": "message_stop"}]
    return sse(events)


def text_block(text: str) -> list[dict]:
    words = text.split(" ")
    return ([{"type": "content_block_start", "content_block": {"type": "text", "text": ""}}]
            + [{"type": "content_block_delta", "delta": {"type": "text_delta", "text": w + (" " if i < len(words) - 1 else "")}}
               for i, w in enumerate(words)]
            + [{"type": "content_block_stop"}])


def cited_block(text: str, url: str, title: str) -> list[dict]:
    return [{"type": "content_block_start", "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "delta": {"type": "citations_delta", "citation": {
                "type": "web_search_result_location", "url": url, "title": title,
                "encrypted_index": "x", "cited_text": text[:40]}}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": text}},
            {"type": "content_block_stop"}]


def error(status: int, kind: str, text: str) -> tuple:
    return status, {"type": "error", "error": {"type": kind, "message": text}}


def search_blocks(query: str) -> list[list[dict]]:
    return [
        [{"type": "content_block_start", "content_block": {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {}}},
         {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": json.dumps({"query": query})}},
         {"type": "content_block_stop"}],
        [{"type": "content_block_start", "content_block": {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
            {"type": "web_search_result", "url": "https://example.com/a", "title": "A", "encrypted_content": "x", "page_age": None}]}},
         {"type": "content_block_stop"}],
    ]


def make_claude_chat(scripts: list, seen: list, ollama_replies=None, ollama_seen=None) -> Chat:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":                     # get_ready() opening the connection
            seen.append({"get": request.url.path})
            return httpx2.Response(200, json={"data": [], "has_more": False, "first_id": None, "last_id": None})
        seen.append({"body": json.loads(request.content), "beta": request.headers.get("anthropic-beta", "")})
        step = scripts.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, tuple):                     # an error reply from the API
            return httpx2.Response(step[0], json=step[1])
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=step)

    c = Chat.__new__(Chat)
    Chat.__init__(c, FakeHouse())
    c.backend = "claude"
    c.client = anthropic.AsyncAnthropic(api_key="test", base_url="http://anthropic.test", max_retries=0,
                                        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    if ollama_replies is not None:
        c.http = httpx.AsyncClient(base_url="http://ollama", transport=ollama_stub(ollama_replies, ollama_seen))
    return c


async def test_searches_the_web_and_speaks_as_it_streams(monkeypatch):
    monkeypatch.setattr(chat_mod, "PLACE", "London")
    monkeypatch.setattr(chat_mod, "COUNTRY", "GB")
    monkeypatch.setattr(chat_mod, "TZ_NAME", "Europe/London")
    seen, spoken, status = [], [], []
    answer = "Lando Norris won on Sunday. It was his fourth win of the season."
    c = make_claude_chat([message(search_blocks("latest f1 winner") + [text_block(answer)])], seen)

    async def say(s):
        spoken.append(s)

    async def on_status(s):
        status.append(s)

    reply = await c.ask("who won the last formula one race", say, on_status)
    assert reply == answer
    assert spoken == ["Lando Norris won on Sunday.", "It was his fourth win of the season."]
    assert status == ["searching"]
    body = seen[0]["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "low"}
    assert body["tools"] == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2,
                              "user_location": {"type": "approximate", "city": "London", "country": "GB",
                                                "timezone": "Europe/London"}}]
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen[0]["beta"]
    assert body["messages"][-1]["content"].endswith("Question: who won the last formula one race")
    assert "web search tool" in body["system"] and "temperature" not in body


async def test_settled_knowledge_needs_no_search():
    seen, status = [], []

    async def on_status(s):
        status.append(s)

    c = make_claude_chat([message([text_block("Canberra is the capital of Australia.")])], seen)
    assert await c.ask("what is the capital of australia", None, on_status) == "Canberra is the capital of Australia."
    assert status == []


async def test_a_paused_search_turn_is_resumed():
    seen = []
    c = make_claude_chat([message(search_blocks("x"), stop_reason="pause_turn"),
                          message([text_block("Found it. The shop opens at nine.")])], seen)
    assert await c.ask("when does the corner shop open tomorrow") == "Found it. The shop opens at nine."
    first, second = seen[0]["body"]["messages"], seen[1]["body"]["messages"]
    assert second[:len(first)] == first
    assert second[-1]["role"] == "assistant" and second[-1]["content"][0]["type"] == "server_tool_use"


async def test_no_internet_answers_from_the_local_model():
    seen, ollama_seen, spoken = [], [], []
    c = make_claude_chat([httpx2.ConnectError("no route")], seen,
                         ollama_replies=[("Paris is the capital.", "stop")], ollama_seen=ollama_seen)

    async def say(s):
        spoken.append(s)

    reply = await c.ask("what is the capital of france", say)
    assert spoken[0] == "I can't reach the internet right now, so this is from memory."
    assert reply.endswith("Paris is the capital.") and len(ollama_seen) == 1


async def test_same_question_again_is_instant_but_follow_ups_are_not():
    seen = []
    c = make_claude_chat([message([text_block("Mount Everest, at 8,849 metres.")]),
                          message([text_block("Because of the Indian plate.")])], seen)
    first = await c.ask("what is the tallest mountain in the world")
    again = await c.ask("What is the tallest mountain in the world?")
    assert again == first and len(seen) == 1
    await c.ask("why is it so tall")
    assert len(seen) == 2


async def test_instant_answers_never_reach_the_internet():
    seen = []
    c = make_claude_chat([], seen)
    assert (await c.ask("what's 12 times 12")) == "12 times 12 is 144."
    assert (await c.ask("say that again")) == "12 times 12 is 144."
    assert seen == []


async def test_declined_question():
    seen = []
    c = make_claude_chat([message([], stop_reason="refusal")], seen)
    assert await c.ask("something it will not answer") == "I can't help with that one."


async def test_sources_are_kept_and_repeated_with_a_remembered_answer():
    seen = []
    c = make_claude_chat([message(search_blocks("bank holiday") + [
        cited_block("The next bank holiday is on the 25th of December. ", "https://www.gov.uk/bank-holidays", "Bank holidays"),
        cited_block("It is Christmas Day.", "https://www.gov.uk/bank-holidays", "Bank holidays")])], seen)
    reply = await c.ask("when is the next bank holiday")
    assert reply == "The next bank holiday is on the 25th of December. It is Christmas Day."
    assert c.last_sources == [{"title": "Bank holidays", "url": "https://www.gov.uk/bank-holidays"}]
    await c.ask("what's 2 plus 2")
    assert c.last_sources == []
    assert await c.ask("When is the next bank holiday?") == reply and len(seen) == 1
    assert c.last_sources == [{"title": "Bank holidays", "url": "https://www.gov.uk/bank-holidays"}]


async def test_filtering_search_only_when_asked(monkeypatch):
    monkeypatch.setattr(chat_mod, "SEARCH_FILTERING", True)
    assert chat_mod._search_tool("claude-opus-5-5")["type"] == "web_search_20260209"
    assert chat_mod._search_tool("claude-haiku-4-5")["type"] == "web_search_20250305"
    monkeypatch.setattr(chat_mod, "SEARCH_FILTERING", False)
    assert chat_mod._search_tool("claude-opus-5-5")["type"] == "web_search_20250305"
    assert chat_mod._has_fallbacks("claude-opus-5-5") and not chat_mod._has_fallbacks("claude-haiku-5-5")


async def test_busy_fast_mode_answers_at_standard_speed(monkeypatch):
    monkeypatch.setattr(chat_mod, "CLAUDE_FAST", True)
    seen = []
    c = make_claude_chat([error(429, "rate_limit_error", "Fast mode limit reached"),
                          message([text_block("It is 21 degrees in Madrid.")])], seen)
    assert await c.ask("how warm is it in madrid") == "It is 21 degrees in Madrid."
    assert seen[0]["body"]["speed"] == "fast" and "speed" not in seen[1]["body"]


async def test_setup_problems_are_explained_out_loud():
    cases = [(error(401, "authentication_error", "invalid x-api-key"), "My API key was rejected"),
             (error(400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API."),
              "The API account is out of credit"),
             (error(400, "invalid_request_error", "Web search is not enabled for your organization."),
              "Web search is switched off for this API account"),
             (error(404, "not_found_error", "model: claude-nonsense"), "The internet model in my settings doesn't exist"),
             (error(529, "overloaded_error", "Overloaded"), "The internet service is busy")]
    for reply, reason in cases:
        spoken = []

        async def say(s):
            spoken.append(s)

        c = make_claude_chat([reply], [], ollama_replies=[("Paris is the capital.", "stop")], ollama_seen=[])
        await c.ask("what is the capital of france", say)
        assert spoken[0] == f"{reason}, so this is from memory.", spoken


async def test_connection_opened_ahead_of_the_question():
    seen = []
    c = make_claude_chat([], seen)
    c.get_ready()
    c.get_ready()                                       # only once a minute
    await asyncio.sleep(0.05)
    assert seen == [{"get": "/v1/models"}]


def test_country_from_the_time_zone():
    from jarvis_core.report import _country
    assert _country("", "Europe/London") == "GB"
    assert _country("uk", "") == "GB"
    assert _country("Britain", "Europe/Paris") == "FR"
    assert _country("", "Mars/Olympus") == ""


async def test_a_refusal_partway_keeps_only_the_notice():
    spoken = []

    async def say(s):
        spoken.append(s)

    c = make_claude_chat([message([text_block("Step one is easy. Step two is")], stop_reason="refusal")], [])
    reply = await c.ask("explain the dangerous thing in detail", say)
    assert spoken == ["Step one is easy.", "I can't finish that answer."]
    assert reply == "I can't finish that answer." and c.history[-1]["content"] == reply


async def test_stop_while_a_paused_turn_carries_on_says_nothing_more():
    spoken = []
    c = make_claude_chat([message(search_blocks("x"), stop_reason="pause_turn"),
                          message([text_block("First sentence. Second sentence. Third sentence.")])], [])

    async def say(s):
        spoken.append(s)
        c.stop()                                        # Stop pressed after the first sentence

    await c.ask("look up something slow for me please", say)
    assert spoken == ["First sentence."]


async def test_a_paused_turn_after_a_model_switch_is_not_sent_back():
    seen = []
    switch = [{"type": "content_block_start", "content_block": {
        "type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-5"}}},
        {"type": "content_block_stop"}]
    c = make_claude_chat([message([switch, text_block("Partly found. ")], stop_reason="pause_turn")], seen)
    reply = await c.ask("look up something slow for me please")
    assert len(seen) == 1 and reply == "Partly found. " + chat_mod.CUT_SHORT
