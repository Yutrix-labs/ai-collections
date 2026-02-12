@echo off
echo ========================================
echo AI Collections Assistant - Start Server
echo ========================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    echo.
)

REM Activate venv
call venv\Scripts\activate.bat

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo.
)

REM Check if Redis is running
echo Checking Redis connection...
python -c "import redis; r=redis.Redis(host='localhost', port=6379); r.ping(); print('Redis is running!')" 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: Cannot connect to Redis!
    echo Please start Redis/Memurai first.
    echo.
    echo Download Redis for Windows:
    echo https://github.com/tporadowski/redis/releases
    echo.
    echo OR download Memurai:
    echo https://www.memurai.com/get-memurai
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting FastAPI Server...
echo ========================================
echo.
echo Server will be available at:
echo   http://localhost:8000
echo.
echo Open test_websocket.html in your browser to test!
echo.
echo Press CTRL+C to stop the server
echo ========================================
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
