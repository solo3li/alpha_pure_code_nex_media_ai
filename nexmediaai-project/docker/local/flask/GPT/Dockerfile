FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY services/GPT/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/GPT .
COPY services/GPT/entrypoint.sh .
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 5007

# Expose port
EXPOSE ${PORT}

# Run the application with Gunicorn
CMD ["./entrypoint.sh"]