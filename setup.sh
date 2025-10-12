#!/bin/bash
# Setup script for Personal Research Agent

set -e

echo "=================================="
echo "Personal Research Agent Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python 3.9+ is available
required_version="3.9"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "❌ Error: Python 3.9 or higher is required"
    echo "   Your version: $python_version"
    exit 1
fi
echo "✅ Python version OK"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Check for RamaLama
echo "Checking for RamaLama..."
if command -v ramalama &> /dev/null; then
    ramalama_version=$(ramalama --version 2>&1 || echo "unknown")
    echo "✅ RamaLama found: $ramalama_version"
else
    echo "⚠️  RamaLama not found (optional)"
    echo "   To use local models, install RamaLama:"
    echo "   pip install ramalama"
    echo "   OR: sudo dnf install ramalama (Fedora/RHEL)"
fi
echo ""

# Create config file
echo "Setting up configuration..."
if [ ! -f ".env" ]; then
    cp config.env.example .env
    echo "✅ Created .env file from template"
    echo "   Please edit .env and add your API keys!"
else
    echo "⚠️  .env file already exists, skipping..."
fi
echo ""

# Test installation
echo "Testing installation..."
python3 -c "import pydantic_ai; print('✅ Pydantic AI imported successfully')"
python3 -c "from duckduckgo_search import DDGS; print('✅ DuckDuckGo search imported successfully')"
echo ""

echo "=================================="
echo "Setup Complete! 🎉"
echo "=================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Set your API key (choose one):"
echo "   • OpenAI: export OPENAI_API_KEY='your-key'"
echo "   • OR use RamaLama: ramalama pull granite"
echo ""
echo "3. Run the demo:"
echo "   python simple_demo.py"
echo ""
echo "4. Or use the full CLI:"
echo "   python research_agent_example.py --mode interactive"
echo ""
echo "For more information, see README.md"
echo ""
