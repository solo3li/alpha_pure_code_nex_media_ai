FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY services/text_to_voice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for audio files
RUN mkdir -p /app/audio_files

# Copy application code
COPY services/text_to_voice/app.py .
COPY services/text_to_voice/config.py .
COPY services/text_to_voice/entrypoint.sh .

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 5008
ENV AUDIO_FOLDER /app/audio_files

# Expose port
EXPOSE ${PORT}

# Create volume for audio files to persist between container restarts
VOLUME ["/app/audio_files"]

# Run the application with custom entrypoint
CMD ["./entrypoint.sh"]