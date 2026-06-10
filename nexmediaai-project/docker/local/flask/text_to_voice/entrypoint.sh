#!/bin/bash
set -e

# Wait for a second before starting to ensure everything is loaded
sleep 1

# Try to run the app directly first (for debugging purposes)
echo "Testing app initialization..."
python -c "from app import app; print('Flask app can be imported successfully')"

# Start Gunicorn with more verbose logging
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --timeout 300 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance \
    app:app