#!/usr/bin/env bash
# Startup script for Flow Video Studio on macOS / Linux

cd "$(dirname "$0")"

echo "==============================================="
echo " Starting Multi-Scene Flow Video Studio (macOS)"
echo "==============================================="

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install Python 3.11+ using brew install python"
    exit 1
fi

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install requirements
echo "Checking dependencies..."
pip install -r requirements.txt --quiet

# Ensure Playwright browser is installed
python3 -m playwright install chromium

# Copy .env if not present
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo ""
echo "Starting web server at http://127.0.0.1:8000"
echo "Open your browser and navigate to http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."
echo ""

python3 server.py
