FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 7418

CMD ["gunicorn", "--bind", "0.0.0.0:7418", "--timeout", "120", "--workers", "4", "app:app"]