"""Speech service: speech-to-text (faster-whisper) and text-to-speech (Piper), on the CPU."""
import io
import logging
import os
import wave

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis.speech")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "en_GB-alan-medium")
MODELS = os.environ.get("MODELS_DIR", "/models")
THREADS = int(os.environ.get("THREADS", "3"))

app = FastAPI(title="J.A.R.V.I.S. speech")
whisper = None
voice = None


@app.on_event("startup")
def load_models() -> None:
    global whisper, voice
    from faster_whisper import WhisperModel
    from piper import PiperVoice

    whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8",
                           cpu_threads=THREADS, download_root=f"{MODELS}/whisper")
    voice = PiperVoice.load(f"{MODELS}/piper/{PIPER_VOICE}.onnx")
    log.info("loaded whisper %s and piper voice %s", WHISPER_MODEL, PIPER_VOICE)


@app.get("/health")
def health():
    return {"ok": whisper is not None and voice is not None}


@app.post("/transcribe")
async def transcribe(request: Request):
    """Body: a WAV file (16 kHz mono is best). Returns the words in it."""
    data = await request.body()
    if len(data) < 1000:
        return JSONResponse({"text": ""})
    segments, _ = whisper.transcribe(
        io.BytesIO(data), language="en", beam_size=1, vad_filter=True,
        condition_on_previous_text=False, without_timestamps=True,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    log.info("heard: %r", text)
    return {"text": text}


@app.get("/tts")
def tts(text: str):
    """Returns a WAV of the text spoken aloud."""
    text = text.strip()[:600]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        voice.synthesize_wav(text or "Nothing to say.", wav)
    return Response(buf.getvalue(), media_type="audio/wav")
