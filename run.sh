#!/bin/bash

# MongoDB Project Management System - Startup Script

echo "🚀 Starting MongoDB Project Management System..."
echo ""

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    ollama serve &
    sleep 3
fi

# Check if the required model is available
if ! ollama list | grep -q "qwen3:0.6b-fp16"; then
    echo "📥 Downloading required AI model..."
    ollama pull qwen3:0.6b-fp16
fi

# Start the FastAPI application
echo "🌐 Starting web server on http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run with uvicorn for better development experience
uvicorn app:app --reload --host 0.0.0.0 --port 8000