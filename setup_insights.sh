#!/bin/bash

# Setup script for MongoDB Insights Agent

echo "MongoDB Insights Agent Setup"
echo "============================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Smithery credentials:"
    echo "   - MCP_API_KEY"
    echo "   - MCP_PROFILE"
    echo ""
else
    echo "✅ .env file already exists"
fi

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
if pip install -r requirements.txt; then
    echo "✅ Python dependencies installed"
else
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

# Instructions
echo ""
echo "Setup complete! Next steps:"
echo "1. Edit .env with your Smithery API credentials"
echo "2. Start the server: python main.py"
echo "3. Test with: python example_insights_client.py"
echo ""
echo "Example queries to try:"
echo "- \"What's the average cycle time by team in the last 30 days?\""
echo "- \"Top 5 blockers this quarter by frequency\""
echo "- \"Show me bug escape rate trends by component\""