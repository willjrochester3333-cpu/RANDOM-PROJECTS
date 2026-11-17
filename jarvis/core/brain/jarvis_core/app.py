"""CORE: connects the house rules to the MQTT broker and serves the dashboard."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiomqtt
import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .chat import OLLAMA_MODEL, Chat
from .house import T_STOP, House
from .relay import Relays
from .store import Store

if os.environ.get("TZ"):
    time.tzset()                      # so dates and times are in the house's time zone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis.app")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None
DB_PATH = os.environ.get("DB_PATH", "jarvis.db")
DINNER_TIMEOUT = float(os.environ.get("DINNER_TIMEOUT", "180"))
SPEECH_URL = os.environ.get("SPEECH_URL", "http://speech:8010").rstrip("/")
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
relays = Relays(house)


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


speech = httpx.AsyncClient(base_url=SPEECH_URL, timeout=httpx.Timeout(120, connect=5))


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(mqtt_loop())
    await chat.start()
    yield
    task.cancel()
    await speech.aclose()


app = FastAPI(title="J.A.R.V.I.S. core", lifespan=lifespan)


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    speak: bool = True
    source: str = Field(default="typed", pattern="^(typed|voice)$")


class VoiceState(BaseModel):
    state: str = Field(pattern="^(idle|listening|thinking|speaking)$")
    text: str = Field(default="", max_length=2000)


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
    await notify({"type": "voice", "state": "thinking", "text": body.text})

    async def on_sentence(sentence: str) -> None:
        # Shown and spoken as soon as the model finishes it, so the answer starts sooner.
        await notify({"type": "partial", "text": sentence})
        if body.speak:
            await house.say(sentence)

    reply = await chat.ask(body.text, on_sentence=on_sentence)
    await notify({"type": "chat", "source": body.source, "text": body.text, "reply": reply})
    await notify({"type": "voice", "state": "idle"})
    return {"reply": reply}


@app.post("/api/voice/stop")
async def voice_stop():
    """Stop talking: end the answer being written and silence the speaker."""
    chat.stop()
    await publish(T_STOP, "stop", False)
    await notify({"type": "voice", "state": "idle"})
    return {"ok": True}


@app.get("/api/report")
async def report(q: str = ""):
    """What the model is told along with a question (all of it when q is empty)."""
    model = OLLAMA_MODEL if chat.backend == "ollama" else chat.backend
    return PlainTextResponse(f"Answering with: {model}\n\n{await chat.report(q)}\n")


# ---- relayed cameras (the kitchen camera): one connection to the camera, shared by everyone ----

def _feed(node: str, kind: str):
    try:
        return relays.feed(node, kind)
    except KeyError:
        raise HTTPException(404, f"No {kind} from a camera called {node}")


@app.get("/api/cameras/{node}/stream.mjpg")
async def camera_stream(node: str):
    feed = _feed(node, "video")

    async def pictures():
        async with feed.watching():
            async for jpeg in feed.frames():
                yield (b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")

    return StreamingResponse(pictures(), media_type="multipart/x-mixed-replace; boundary=FRAME",
                             headers={"Cache-Control": "no-cache, private"})


@app.get("/api/cameras/{node}/audio.wav")
async def camera_audio(node: str):
    feed = _feed(node, "audio")

    async def sound():
        async with feed.watching():
            async for chunk in feed.chunks():
                yield chunk

    return StreamingResponse(sound(), media_type="audio/wav", headers={"Cache-Control": "no-cache, private"})


@app.get("/api/cameras/{node}/snapshot.jpg")
async def camera_snapshot(node: str):
    feed = _feed(node, "video")
    if feed.connected and feed.frame:
        return Response(feed.frame, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    try:
        r = await relays.http.get(relays.snapshot_url(node))
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "The camera did not answer")
    return Response(r.content, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@app.post("/api/listen")
async def listen():
    """Start listening on the server's microphone, as if the wake word had been said."""
    await house.listen()
    return {"ok": True}


@app.post("/api/voice/state")
async def voice_state(body: VoiceState):
    """The microphone service reports what it is doing, so dashboards can show it."""
    await notify({"type": "voice", "state": body.state, "text": body.text})
    return {"ok": True}


@app.post("/api/transcribe")
async def transcribe(request: Request):
    """Body: WAV audio. Returns the words in it, via the speech service."""
    data = await request.body()
    if len(data) > 10_000_000:
        raise HTTPException(413, "audio too long")
    try:
        r = await speech.post("/transcribe", content=data, headers={"Content-Type": "audio/wav"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("speech service transcribe failed: %s", e)
        raise HTTPException(503, "speech service unavailable")
    return r.json()


@app.get("/api/tts")
async def tts(text: str):
    """Returns a WAV of the text, spoken by the speech service."""
    try:
        r = await speech.get("/tts", params={"text": text[:600]})
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("speech service tts failed: %s", e)
        raise HTTPException(503, "speech service unavailable")
    return Response(r.content, media_type="audio/wav")


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
