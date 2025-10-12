#!/bin/bash
# Quick start script - runs the simple demo

echo "🔬 Personal Research Agent - Quick Start"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  Warning: OPENAI_API_KEY not set"
    echo ""
    echo "To use OpenAI models:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    echo ""
    echo "OR to use RamaLama (local, free):"
    echo "  ramalama pull granite"
    echo "  python research_agent_example.py --use-ramalama"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Running simple demo..."
echo ""
python simple_demo.py
