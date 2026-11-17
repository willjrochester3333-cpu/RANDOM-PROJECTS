import asyncio
import json

import pytest

from jarvis_core import house as h
from jarvis_core.house import House
from jarvis_core.store import Store


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "PRESS_DEBOUNCE_S", 0)
    sent, events = [], []

    async def publish(topic, payload, retain):
        sent.append((topic, payload, retain))

    async def notify(event):
        events.append(event)

    return House(Store(str(tmp_path / "t.db")), publish, notify, dinner_timeout=0.05), sent, events


def last(sent, topic):
    return [p for t, p, _ in sent if t == topic][-1]


async def test_dinner_call_ack_and_timeout(rig):
    house, sent, events = rig
    await house.handle(h.T_DINNER, "pressed")
    assert house.dinner["state"] == "calling"
    assert last(sent, h.T_LED) == "blink"
    assert last(sent, h.T_ALERT) == "dinner"
    assert last(sent, h.T_SAY) == "Dinner is ready."
    assert any(e["type"] == "say" for e in events)

    await house.handle(h.T_ACK, "pressed")
    assert house.dinner["state"] == "acknowledged"
    assert house.dinner["ack_by"] == "beacon"
    assert last(sent, h.T_LED) == "solid"
    assert last(sent, h.T_ALERT) == "clear"

    await asyncio.sleep(0.12)
    assert house.dinner["state"] == "idle"
    assert last(sent, h.T_LED) == "off"


async def test_ack_without_call_does_nothing(rig):
    house, sent, _ = rig
    assert await house.ack_dinner("console") is False
    assert sent == []


async def test_retained_press_is_ignored(rig):
    house, _, _ = rig
    await house.handle(h.T_DINNER, "pressed", retained=True)
    assert house.dinner["state"] == "idle"


async def test_debounce(rig, monkeypatch):
    house, sent, _ = rig
    monkeypatch.setattr(h, "PRESS_DEBOUNCE_S", 2)
    await house.handle(h.T_DINNER, "pressed")
    await house.handle(h.T_DINNER, "pressed")
    assert [p for t, p, _ in sent if t == h.T_SAY] == ["Dinner is ready."]


async def test_weather_stored_and_validated(rig):
    house, _, _ = rig
    await house.handle(h.T_WEATHER, json.dumps({"temp_c": 8.44, "humidity": 71, "pressure_hpa": 1009.2}))
    assert house.weather["temp_c"] == 8.4
    assert house.store.latest_weather()["humidity"] == 71
    assert house.snapshot()["weather"]["stale"] is False

    for bad in ("not json", '{"temp_c": 999, "humidity": 50, "pressure_hpa": 1000}', '{"temp_c": 5}'):
        await house.handle(h.T_WEATHER, bad)
    assert house.weather["temp_c"] == 8.4
    assert len(house.store.history(1)) == 1


async def test_status_and_resync(rig):
    house, sent, _ = rig
    await house.handle("jarvis/beacon/status", "online", retained=True)
    await house.handle("jarvis/kitchen/status", "offline", retained=True)
    assert house.nodes["beacon"]["online"] is True
    assert house.nodes["kitchen"]["online"] is False

    await house.call_dinner()
    sent.clear()
    await house.resync()
    assert (h.T_LED, "blink", True) in sent and (h.T_ALERT, "dinner", True) in sent


async def test_camera_stream_announced_and_removed(rig):
    house, _, events = rig
    url = "http://192.168.1.60:8081/stream.mjpg?key=abc"
    await house.handle("jarvis/camera/stream", url, retained=True)
    assert house.snapshot()["cameras"] == {"camera": {"name": "Camera", "video": url, "audio": None}}
    assert events[-1]["state"]["cameras"]["camera"]["video"] == url
    await house.handle("jarvis/camera/stream", "")
    assert house.snapshot()["cameras"] == {}
    await house.handle("jarvis/camera/stream", "javascript:alert(1)")
    assert house.snapshot()["cameras"] == {}


async def test_relayed_camera_hides_its_own_address(rig):
    house, _, _ = rig
    announce = ('{"name": "Kitchen camera", "video": "http://192.168.1.77/stream.mjpg?key=k1", '
                '"audio": "http://192.168.1.77/audio.wav?key=k1", "relay": true}')
    await house.handle("jarvis/kitchen/stream", announce, retained=True)
    assert house.snapshot()["cameras"]["kitchen"] == {
        "name": "Kitchen camera",
        "video": "/api/cameras/kitchen/stream.mjpg",
        "audio": "/api/cameras/kitchen/audio.wav",
    }
    assert "k1" not in str(house.snapshot())
    assert house.cameras["kitchen"]["video"].endswith("key=k1")      # the server still knows it
    for bad in ('{"video": "ftp://x"}', "{not json", '{"name": "x"}'):
        await house.handle("jarvis/kitchen/stream", bad)
        assert "kitchen" not in house.cameras
