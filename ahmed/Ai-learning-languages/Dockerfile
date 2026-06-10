# ─── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# System dependencies: ffmpeg (Whisper audio decode), git, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

# 1. Upgrade pip + build tools into the GLOBAL env
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 2. Copy requirements and install everything EXCEPT openai-whisper
COPY requirements.txt .
RUN grep -iv "openai-whisper" requirements.txt \
    | pip install --no-cache-dir -r /dev/stdin

# 3. Install openai-whisper with --no-build-isolation
#    This makes pip reuse our already-installed setuptools (pkg_resources)
#    instead of creating a clean isolated env that lacks it.
RUN pip install --no-cache-dir --no-build-isolation openai-whisper==20231117

# 4. Pre-download Whisper "base" model into the image (avoids cold-start delay)
RUN python -c "import whisper; whisper.load_model('base')"

# 5. Copy the rest of the application
COPY . .

# Create temp dir for audio files
RUN mkdir -p /app/temp

# ─── Config ────────────────────────────────────────────────────────────────────
EXPOSE 5000

ENV FLASK_APP=app.py \
    FLASK_RUN_HOST=0.0.0.0 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

# ─── Run ───────────────────────────────────────────────────────────────────────
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
