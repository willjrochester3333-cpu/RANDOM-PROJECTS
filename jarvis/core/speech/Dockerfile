FROM python:3.12-slim
# Which speech-to-text model and voice to bake in. Bigger Whisper models hear better but
# take longer: tiny.en < base.en < small.en. Voices: https://rhasspy.github.io/piper-samples/
ARG WHISPER_MODEL=base.en
ARG PIPER_VOICE=en_GB-alan-medium
ENV WHISPER_MODEL=$WHISPER_MODEL PIPER_VOICE=$PIPER_VOICE MODELS_DIR=/models

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the models at build time, so the service starts offline afterwards.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('$WHISPER_MODEL', device='cpu', compute_type='int8', download_root='/models/whisper')" \
 && python -m piper.download_voices "$PIPER_VOICE" --download-dir /models/piper

COPY app.py .
EXPOSE 8010
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
