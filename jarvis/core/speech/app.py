"""Speech service: speech-to-text (faster-whisper) and text-to-speech (Piper), on the CPU."""
import io
import logging
import os
import wave

import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis.speech")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "en_GB-alan-medium")
MODELS = os.environ.get("MODELS_DIR", "/models")
THREADS = int(os.environ.get("THREADS", "4"))          # Whisper: runs while the model is idle
TTS_THREADS = int(os.environ.get("TTS_THREADS", "2"))  # Piper: runs while the model writes, so stay small

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
    model_path = f"{MODELS}/piper/{PIPER_VOICE}.onnx"
    voice = PiperVoice.load(model_path)
    # Piper's own session uses every core and fights the language model for them; replace it
    # with one limited to TTS_THREADS.
    try:
        import onnxruntime
        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = TTS_THREADS
        opts.inter_op_num_threads = 1
        voice.session = onnxruntime.InferenceSession(model_path, sess_options=opts,
                                                     providers=["CPUExecutionProvider"])
    except Exception as e:                       # a newer Piper may differ: keep its own session
        log.warning("could not limit Piper's threads (%s); using its defaults", e)
    # First runs are slow while things are set up: do them now, not on the first question.
    hear(np.zeros(16000, np.float32))
    speak("Ready.")
    log.info("loaded whisper %s and piper voice %s", WHISPER_MODEL, PIPER_VOICE)


def hear(audio: np.ndarray) -> str:
    # The recording is already trimmed to the speech, so Whisper's own speech detection is
    # skipped; temperature 0 means one decoding pass, never retries.
    segments, _ = whisper.transcribe(
        audio, language="en", beam_size=1, best_of=1, temperature=0.0, vad_filter=False,
        condition_on_previous_text=False, without_timestamps=True,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def speak(text: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        voice.synthesize_wav(text or "Nothing to say.", wav)
    return buf.getvalue()


@app.get("/health")
def health():
    return {"ok": whisper is not None and voice is not None}


@app.post("/transcribe")
async def transcribe(request: Request):
    """Body: a WAV file (16 kHz mono is best). Returns the words in it."""
    data = await request.body()
    if len(data) < 1000:
        return JSONResponse({"text": ""})
    try:
        audio = wav_to_samples(data)
    except (wave.Error, EOFError, ValueError) as e:
        log.warning("bad audio: %s", e)
        return JSONResponse({"text": ""})
    text = await run_in_threadpool(hear, audio)      # keeps the service answering meanwhile
    log.info("heard: %r", text)
    return {"text": text}


def wav_to_samples(data: bytes) -> np.ndarray:
    """Decode a 16-bit PCM WAV into the 16 kHz mono float array Whisper wants, without PyAV."""
    with wave.open(io.BytesIO(data)) as w:
        channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"need 16-bit audio, got {width * 8}-bit")
    pcm = np.frombuffer(frames, np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        n = int(len(pcm) * 16000 / rate)
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
    return pcm


@app.get("/tts")
def tts(text: str):
    """Returns a WAV of the text spoken aloud."""
    return Response(speak(text.strip()[:600]), media_type="audio/wav")
