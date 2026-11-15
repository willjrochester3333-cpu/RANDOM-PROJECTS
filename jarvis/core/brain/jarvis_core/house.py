"""House state and rules. No network code here: MQTT and the web layer are injected."""
import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

log = logging.getLogger("jarvis.house")

T_WEATHER = "jarvis/outpost/weather"
T_DINNER = "jarvis/kitchen/dinner"
T_LED = "jarvis/kitchen/led"
T_ALERT = "jarvis/beacon/alert"
T_ACK = "jarvis/beacon/ack"
T_SAY = "jarvis/console/say"

WEATHER_STALE_S = 300      # no reading for 5 minutes = outpost is in trouble
PRESS_DEBOUNCE_S = 2

Publish = Callable[[str, str, bool], Awaitable[None]]   # topic, payload, retain
Notify = Callable[[dict], Awaitable[None]]


class House:
    def __init__(self, store, publish: Publish, notify: Notify, dinner_timeout: float = 180):
        self.store = store
        self._publish = publish
        self._notify = notify
        self.dinner_timeout = dinner_timeout
        self.nodes: dict[str, dict] = {}
        self.cameras: dict[str, str] = {}     # node name -> live stream address
        self.weather: dict | None = store.latest_weather()
        self.dinner = {"state": "idle", "since": None, "ack_by": None}
        self._last_press = 0.0
        self._timer: asyncio.Task | None = None

    # ---- incoming MQTT ----

    async def handle(self, topic: str, payload: str, retained: bool = False) -> None:
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != "jarvis":
            return
        node, leaf = parts[1], parts[2]

        if leaf == "status":
            self.nodes[node] = {"online": payload == "online", "since": time.time()}
            await self._changed()
        elif leaf == "stream":
            if payload.startswith(("http://", "https://")):
                self.cameras[node] = payload
            else:
                self.cameras.pop(node, None)
            await self._changed()
        elif topic == T_WEATHER:
            await self._on_weather(payload, retained)
        elif topic == T_DINNER and payload == "pressed" and not retained:
            await self.call_dinner()
        elif topic == T_ACK and payload == "pressed" and not retained:
            await self.ack_dinner("beacon")
        # T_LED, T_ALERT and T_SAY are our own messages echoed back: ignore.

    async def _on_weather(self, payload: str, retained: bool) -> None:
        try:
            d = json.loads(payload)
            t, h, p = float(d["temp_c"]), float(d["humidity"]), float(d["pressure_hpa"])
        except (ValueError, KeyError, TypeError):
            log.warning("bad weather payload: %r", payload[:120])
            return
        if not (-60 <= t <= 70 and 0 <= h <= 100 and 800 <= p <= 1100):
            log.warning("weather reading out of range: %r", payload[:120])
            return
        if retained and self.weather:
            return   # an old retained copy must not overwrite or duplicate history
        now = time.time()
        self.weather = {"ts": int(now), "temp_c": round(t, 1), "humidity": round(h, 1), "pressure_hpa": round(p, 1)}
        await asyncio.to_thread(self.store.add_weather, now, t, h, p)
        await self._changed()

    # ---- dinner ----

    async def call_dinner(self) -> bool:
        now = time.time()
        if now - self._last_press < PRESS_DEBOUNCE_S:
            return False
        self._last_press = now
        self.dinner = {"state": "calling", "since": now, "ack_by": None}
        self._restart_timer()
        await self._publish(T_LED, "blink", True)
        await self._publish(T_ALERT, "dinner", True)
        await self.say("Dinner is ready.")
        await self._changed()
        return True

    async def ack_dinner(self, by: str) -> bool:
        if self.dinner["state"] != "calling":
            return False
        self.dinner = {**self.dinner, "state": "acknowledged", "ack_by": by}
        await self._publish(T_LED, "solid", True)
        await self._publish(T_ALERT, "clear", True)
        await self._changed()
        return True

    async def clear_dinner(self) -> None:
        if self._timer and self._timer is not asyncio.current_task():
            self._timer.cancel()
        self._timer = None
        self.dinner = {"state": "idle", "since": None, "ack_by": None}
        await self._publish(T_LED, "off", True)
        await self._publish(T_ALERT, "clear", True)
        await self._changed()

    def _restart_timer(self) -> None:
        if self._timer:
            self._timer.cancel()

        async def expire():
            await asyncio.sleep(self.dinner_timeout)
            await self.clear_dinner()

        self._timer = asyncio.create_task(expire())

    async def resync(self) -> None:
        """Re-send output states after (re)connecting to the broker."""
        state = self.dinner["state"]
        await self._publish(T_LED, {"idle": "off", "calling": "blink", "acknowledged": "solid"}[state], True)
        await self._publish(T_ALERT, "dinner" if state == "calling" else "clear", True)

    # ---- outputs ----

    async def say(self, text: str) -> None:
        await self._publish(T_SAY, text, False)
        await self._notify({"type": "say", "text": text})

    def snapshot(self) -> dict:
        now = time.time()
        weather = None
        if self.weather:
            age = now - self.weather["ts"]
            weather = {**self.weather, "age_s": int(age), "stale": age > WEATHER_STALE_S}
        return {"time": int(now), "weather": weather, "nodes": self.nodes, "dinner": self.dinner,
                "cameras": self.cameras}

    async def _changed(self) -> None:
        await self._notify({"type": "state", "state": self.snapshot()})
