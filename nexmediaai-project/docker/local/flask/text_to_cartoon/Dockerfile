# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY services/text_to_cartoon/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY services/text_to_cartoon .
RUN mkdir -p uploads

# Expose port (Gunicorn will use this)
EXPOSE 5006

# Run with Gunicorn
CMD ["gunicorn","--bind", "0.0.0.0:5006","--workers", "4","--timeout", "1000","--access-logfile", "-","app:app"]

