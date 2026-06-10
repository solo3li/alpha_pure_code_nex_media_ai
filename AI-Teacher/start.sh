#!/bin/bash

# AI Spanish Teacher - Docker Startup Script

echo "🇪🇸 Starting AI Spanish Teacher..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp env.example .env
    echo "📝 Please edit .env file and add your OPENROUTER_API_KEY"
    echo "   Then run this script again."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create temp directory if it doesn't exist
mkdir -p temp

# Start the application
echo "🐳 Starting Docker containers..."
docker-compose up --build

echo "✅ AI Spanish Teacher is running!"
echo "🌐 Open your browser and go to: http://localhost:5000"
