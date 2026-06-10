FROM python:3.9-slim-bullseye

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pre-install PyTorch CPU version first
COPY services/voice_to_text/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and cache whisper model


COPY services/voice_to_text/app.py .





EXPOSE 5005

# Gunicorn configuration
CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--timeout", "300", "--workers=1", "app:app"]