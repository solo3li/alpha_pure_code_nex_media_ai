FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install numpy first to avoid conflicts
RUN pip install --no-cache-dir "numpy>=1.24.0,<2.0.0"

# Install compatible PyTorch stack (all versions must match)
RUN pip install --no-cache-dir --upgrade \
    torch==2.1.2 \
    torchvision==0.16.2 \
    torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cpu

# Install transformers/accelerate from PyPI
RUN pip install --no-cache-dir --upgrade \
    transformers==4.40.2 \
    accelerate==0.28.0 \
    Pillow \
    --default-timeout=100 \
    --retries 5

# Copy requirements file for caching
COPY services/img_to_txt/requirements.txt .

# Install other dependencies
RUN pip install --no-cache-dir \
    --default-timeout=3600 \
    --retries=10 \
    -r requirements.txt

# Pre-download model with timeout protection
RUN python3 -c "\
import socket; \
socket.setdefaulttimeout(3600); \
from transformers import BlipProcessor, BlipForConditionalGeneration; \
BlipProcessor.from_pretrained('Salesforce/blip-image-captioning-base', cache_dir='/app/models'); \
BlipForConditionalGeneration.from_pretrained('Salesforce/blip-image-captioning-base', cache_dir='/app/models')"

# Copy application code
COPY . .

# Create upload directory
RUN mkdir -p /app/uploads && chmod a+rwx /app/uploads

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
EXPOSE 5004

CMD ["flask", "run", "--host=0.0.0.0", "--port=5004"]