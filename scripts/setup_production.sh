#!/bin/bash
# setup_production.sh - Initial Mnemosyne setup on a production server

set -e

echo "🔧 Starting Mnemosyne setup (v0.3 File-First)..."

# 1. Check environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

echo "📥 Installing dependencies..."
.venv/bin/pip install -r requirements.txt

# 2. Create directory structure
echo "📂 Creating directory structure..."
mkdir -p knowledge
mkdir -p data
mkdir -p logs

# Kùzu fix: if kuzu_db or kuzu_main exist as files (common mistake), remove them
if [ -f "data/kuzu_db" ]; then rm "data/kuzu_db"; fi
if [ -f "data/kuzu_main" ]; then rm "data/kuzu_main"; fi

# 3. Configure .env
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file (remember to fill it in!)..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        echo "OPENAI_API_KEY=your_key_here" > .env
    fi
fi

# 4. Cold Boot (index existing files)
echo "🧠 Running Cold Boot (indexing existing files)..."
export PYTHONPATH=.
.venv/bin/python3 workers/file_watcher.py --once

echo ""
echo "✅ Setup completed successfully!"
echo "--------------------------------------------------"
echo "Next steps:"
echo "1. Edit the .env file with your API keys."
echo "2. Place your .md files in the 'knowledge/' directory."
echo "3. Start the system with: ./scripts/start.sh"
echo "--------------------------------------------------"
