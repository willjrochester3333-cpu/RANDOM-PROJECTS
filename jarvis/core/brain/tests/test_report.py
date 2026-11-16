from jarvis_core.report import Forecast, describe, topics

SNAP = {
    "weather": {"ts": 0, "temp_c": 8.4, "humidity": 71, "pressure_hpa": 1009.2, "age_s": 30, "stale": False},
    "dinner": {"state": "idle"},
    "nodes": {"core": {"online": True}, "beacon": {"online": False}},
    "cameras": {},
}
HIST = [{"ts": i * 3600, "temp_c": 5 + i % 4, "humidity": 70, "pressure_hpa": 1012 - i * 0.5} for i in range(24)]


def test_topics_pick_relevant_sections():
    assert topics("do I need an umbrella tomorrow?") == {"weather"}
    assert topics("is dinner ready") == {"dinner"}
    assert topics("is the beacon online?") == {"devices"}
    assert topics("who wrote Hamlet?") == set()
    assert topics("") == {"weather", "dinner", "devices"}


def test_general_question_gets_a_short_report():
    text = describe(SNAP, HIST, Forecast(), "who wrote Hamlet?")
    assert text.startswith("Now: ") and "Outside: 8 degrees." in text
    assert "Last 24 hours" not in text and "Devices" not in text and "Dinner" not in text
    assert len(text) < 120


def test_weather_question_gets_weather_and_trend():
    text = describe(SNAP, HIST, Forecast(), "how cold is it outside?")
    assert "8.4 degrees C" in text and "Last 24 hours: low 5.0, high 8.0" in text
    assert "Pressure falling" in text and "Devices" not in text


def test_dinner_shown_when_called_even_if_not_asked():
    snap = {**SNAP, "dinner": {"state": "calling"}}
    assert "Dinner is ready" in describe(snap, HIST, Forecast(), "what is the capital of France")


def test_empty_question_gets_everything():
    text = describe(SNAP, HIST, Forecast(), "")
    assert all(k in text for k in ("Last 24 hours", "Dinner has not", "Devices online: core", "Devices offline: beacon"))
