#!/bin/bash
set -e

# Wait for a second before starting to ensure everything is loaded
sleep 1

# Try to run the app directly first (for debugging purposes)
echo "Testing app initialization..."
python -c "from app import app; print('Flask app can be imported successfully')"

# Start Gunicorn with appropriate configurations
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5007 \
    --workers 4 \
    --timeout 120 \
    --log-level debug \
    app:app