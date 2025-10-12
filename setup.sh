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

# Prefer using uv (https://github.com/astral-sh/uv) as the project manager
echo "Checking for uv (Astral uv project manager)..."
USED_UV=0
if command -v uv >/dev/null 2>&1; then
    uv_version=$(uv --version 2>&1 || echo "unknown")
    echo "✅ uv found: $uv_version"
    USED_UV=1
    echo "Setting up project environment with uv..."

    # Create or ensure a project virtual environment (.venv)
    echo "Creating/ensuring virtual environment with uv (creates .venv)..."
    uv venv || true

    # Install/sync dependencies using uv (reads pyproject.toml / lockfile)
    echo "Installing dependencies with uv sync (pyproject.toml / lockfile)..."
    uv sync || true
    echo "✅ uv sync finished (if any deps were configured)"
else
    echo "⚠️  uv not found — falling back to venv + pip (original behavior)"

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
    # shellcheck disable=SC1091
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    echo ""

    # Upgrade pip
    echo "Upgrading pip..."
    pip install --upgrade pip
    echo "✅ pip upgraded"
    echo ""

    # Install dependencies from pyproject.toml by installing package (fallback)
    echo "Installing Python dependencies (pip fallback installing package)..."
    pip install .
    echo "✅ Dependencies installed via pip install ."
    echo ""
fi

# Check for RamaLama
echo "Checking for RamaLama..."
if command -v ramalama &> /dev/null; then
    echo "✅ RamaLama found"
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
if [ "$USED_UV" -eq 1 ]; then
    echo "Running tests inside uv environment..."
    uv run python -c "import pydantic_ai; print('✅ Pydantic AI imported successfully')"
    uv run python -c "from duckduckgo_search import DDGS; print('✅ DuckDuckGo search imported successfully')"
else
    python3 -c "import pydantic_ai; print('✅ Pydantic AI imported successfully')"
    python3 -c "from duckduckgo_search import DDGS; print('✅ DuckDuckGo search imported successfully')"
fi
echo ""

echo "=================================="
echo "Setup Complete! 🎉"
echo "=================================="
echo ""
echo "Next steps:"
echo ""
echo "If you used uv (recommended):"
echo "  • Run the demo with uv (will run inside the project's .venv):"
echo "      uv run python simple_demo.py"
echo "  • Or run the interactive CLI:"
echo "      uv run python research_agent_example.py --mode interactive"
echo ""
echo "If you fell back to venv + pip:"
echo " 1. Activate the virtual environment:"
echo "      source venv/bin/activate"
echo " 2. Set your API key (choose one):"
echo "      • OpenAI: export OPENAI_API_KEY='your-key'"
echo "      • OR use RamaLama: ramalama pull granite"
echo " 3. Run the demo:"
echo "      python simple_demo.py"
echo " 4. Or use the full CLI:"
echo "      python research_agent_example.py --mode interactive"
echo ""
echo "For more information, see README.md"
echo ""
