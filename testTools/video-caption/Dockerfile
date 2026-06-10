FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (minimal font packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3.10-distutils \
    python3-pip \
    ffmpeg \
    build-essential \
    wget \
    curl \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Basic font packages that exist in Ubuntu 22.04
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links for Python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.10 /usr/bin/python

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .

# Install PyTorch with CUDA support
RUN pip install --no-cache-dir torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1+cu121 --index-url https://download.pytorch.org/whl/cu121

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install Whisper
RUN pip install --no-cache-dir openai-whisper

# Copy application files
COPY . /app

# Create fonts directory and copy all fonts
RUN mkdir -p /app/fonts /app/.cache/torch /app/.cache/whisper

# Copy your pre-downloaded fonts
COPY fonts/ /app/fonts/

# Set font permissions and update font cache
RUN chmod -R 644 /app/fonts/* && \
    fc-cache -fv

# Environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5004
ENV PYTHONUNBUFFERED=1
ENV FONT_FOLDER=/app/fonts

# CUDA environment variables
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV CUDA_VISIBLE_DEVICES=0
ENV NCCL_P2P_DISABLE=1
ENV TOKENIZERS_PARALLELISM=false

# Performance settings
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV CUDA_LAUNCH_BLOCKING=1

# Whisper settings
ENV WHISPER_MODEL_SIZE=small
ENV TORCH_HOME=/app/.cache/torch

# Font configuration
ENV FONTCONFIG_PATH=/etc/fonts
ENV FC_LANG=en:ar

# Set permissions
RUN chmod -R 755 /app

EXPOSE 5004

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5004/health || exit 1

# Start command
CMD ["python", "-c", "import multiprocessing; multiprocessing.set_start_method('spawn', force=True); import app; app.app.run(host='0.0.0.0', port=5004, threaded=True)"]