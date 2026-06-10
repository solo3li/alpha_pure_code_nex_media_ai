FROM python:3.9-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY services/bg_remover/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download u2net.onnx model
RUN python3 -c "from rembg import new_session; new_session('u2net')"

# Copy application
COPY services/bg_remover /app

# Create directories
RUN mkdir -p /tmp/uploads /tmp/processed

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

EXPOSE 5000

# Gunicorn with increased timeout
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "1000", "app:app"]
