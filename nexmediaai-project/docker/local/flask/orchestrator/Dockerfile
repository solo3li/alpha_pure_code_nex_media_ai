FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./services/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./services/orchestrator /app

EXPOSE 5550

CMD ["gunicorn", "--bind", "0.0.0.0:5550", "--workers", "2", "--timeout", "120","--access-logfile", "-", "orchestrator:app"]