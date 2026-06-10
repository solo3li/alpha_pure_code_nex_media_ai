#!/bin/bash
set -e

# Wait a moment before starting
sleep 1

# Test app import
echo "Testing app initialization..."
python -c "from app import app; print('Flask app can be imported successfully')"

# Start Gunicorn with gevent async workers
echo "Starting Gunicorn with gevent..."
exec gunicorn --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --worker-class gevent \
    --timeout 200 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance \
    app:app
