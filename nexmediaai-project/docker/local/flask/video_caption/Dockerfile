# Start with a Python base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# - ffmpeg is required by whisper and moviepy
# - build-essential and other libs might be needed for some Python package installations
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    # Add any other system libraries required by your Python packages
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY services/video_caption/requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install moviepy

# Copy the Flask application code into the container
COPY services/video_caption /app
# --- Font Handling ---
# Create a directory for fonts if it doesn't exist from COPY . .
RUN mkdir -p /app/fonts
# Copy your font files into the /app/fonts directory in the container.
# Replace with your actual font file names and paths.
# Example:
# COPY fonts/Arial.ttf /app/fonts/Arial.ttf
# COPY fonts/Poppins-Bold.ttf /app/fonts/Poppins-Bold.ttf
# COPY fonts/NotoNaskhArabic-Regular.ttf /app/fonts/NotoNaskhArabic-Regular.ttf
# Ensure these paths are relative to the Dockerfile's location (your video_caption_processor service directory)
# If you have a 'fonts' subdirectory in your service's code:
COPY ./fonts/ /app/fonts/

# Set environment variables (can also be set at runtime)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5002
ENV PYTHONUNBUFFERED=1  
ENV FONT_FOLDER=/app/fonts  

# Expose the port the app runs on
EXPOSE 5003

# Define the command to run the application using Gunicorn for production
# Adjust workers based on your server's CPU cores. Typically 2-4 workers per core.
# Timeout is important for long-running video processing tasks if Gunicorn handles the request directly.
# However, with Flask's threading and polling for /process, Gunicorn timeout might apply to the initial request.
# For long polling or SSE, Gunicorn needs to be configured for that (e.g. using gevent workers).
# For simplicity with Flask's default server + threading for /process:
# CMD ["flask", "run"]
# For Gunicorn (recommended for production):
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "4", "--threads", "2", "--timeout", "1800", "app:app"]
# The timeout here (1800s = 30min) should be longer than your longest expected video processing time if Gunicorn
# is directly handling the /process route before handing off to Flask's internal polling.
# If Flask's /process endpoint itself is managing the long poll with its own timeout, Gunicorn's timeout
# might be less critical for that specific route once the request is handed to Flask.
# For SSE with /progress, you might need `worker-class = "gevent"` or similar for Gunicorn.
