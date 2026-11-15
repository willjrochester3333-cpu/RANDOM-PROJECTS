"""CORE: connects the house rules to the MQTT broker and serves the dashboard."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiomqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .chat import Chat
from .house import House
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis.app")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None
DB_PATH = os.environ.get("DB_PATH", "jarvis.db")
DINNER_TIMEOUT = float(os.environ.get("DINNER_TIMEOUT", "180"))
STATIC = Path(__file__).parent / "static"

sockets: set[WebSocket] = set()
mqtt: aiomqtt.Client | None = None


async def publish(topic: str, payload: str, retain: bool) -> None:
    if mqtt is None:
        log.warning("broker offline, dropped %s=%s", topic, payload)
        return
    try:
        await mqtt.publish(topic, payload, qos=1, retain=retain)
    except aiomqtt.MqttError as e:
        log.warning("publish failed for %s: %s", topic, e)


async def notify(event: dict) -> None:
    for ws in list(sockets):
        try:
            await ws.send_json(event)
        except Exception:
            sockets.discard(ws)


house = House(Store(DB_PATH), publish, notify, DINNER_TIMEOUT)
chat = Chat(house)


async def mqtt_loop() -> None:
    global mqtt
    while True:
        try:
            async with aiomqtt.Client(
                MQTT_HOST, MQTT_PORT, username=MQTT_USER, password=MQTT_PASSWORD,
                identifier="jarvis-core",
                will=aiomqtt.Will("jarvis/core/status", "offline", qos=1, retain=True),
            ) as client:
                mqtt = client
                log.info("connected to broker %s:%s", MQTT_HOST, MQTT_PORT)
                await client.publish("jarvis/core/status", "online", qos=1, retain=True)
                await client.subscribe("jarvis/#", qos=1)
                await house.resync()
                async for msg in client.messages:
                    payload = msg.payload.decode("utf-8", "replace") if isinstance(msg.payload, bytes) else str(msg.payload)
                    try:
                        await house.handle(msg.topic.value, payload, bool(msg.retain))
                    except Exception:
                        log.exception("error handling %s", msg.topic.value)
        except aiomqtt.MqttError as e:
            log.warning("broker connection lost (%s), retrying in 5 s", e)
        finally:
            mqtt = None
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(mqtt_loop())
    yield
    task.cancel()


app = FastAPI(title="J.A.R.V.I.S. core", lifespan=lifespan)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speak: bool = True


class SayIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
async def state():
    return {**house.snapshot(), "broker": mqtt is not None}


@app.get("/api/weather/history")
async def weather_history(hours: float = 24):
    hours = min(max(hours, 1), 24 * 365)
    return await asyncio.to_thread(house.store.history, hours)


@app.post("/api/dinner/call")
async def dinner_call():
    return {"ok": await house.call_dinner()}


@app.post("/api/dinner/ack")
async def dinner_ack():
    return {"ok": await house.ack_dinner("console")}


@app.post("/api/dinner/clear")
async def dinner_clear():
    await house.clear_dinner()
    return {"ok": True}


@app.post("/api/chat")
async def chat_endpoint(body: ChatIn):
    reply = await chat.ask(body.text)
    if body.speak:
        await house.say(reply)
    return {"reply": reply}


@app.post("/api/say")
async def say(body: SayIn):
    await house.say(body.text)
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    sockets.add(ws)
    try:
        await ws.send_json({"type": "state", "state": house.snapshot()})
        while True:
            await ws.receive_text()   # clients only listen; this detects disconnects
    except WebSocketDisconnect:
        pass
    finally:
        sockets.discard(ws)
