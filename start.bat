@echo off
echo 🇪🇸 Starting AI Spanish Teacher...

REM Check if .env file exists
if not exist .env (
    echo ⚠️  .env file not found. Creating from template...
    copy env.example .env
    echo 📝 Please edit .env file and add your OPENROUTER_API_KEY
    echo    Then run this script again.
    pause
    exit /b 1
)


REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Create temp directory if it doesn't exist
if not exist temp mkdir temp

REM Start the application
echo 🐳 Starting Docker containers...
docker-compose up --build

echo ✅ AI Spanish Teacher is running!
echo 🌐 Open your browser and go to: http://localhost:5000
pause
