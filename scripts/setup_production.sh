#!/bin/bash
# setup_production.sh - Configurazione iniziale Mnemosyne su server di produzione

set -e

echo "🔧 Inizio configurazione Mnemosyne (v0.3 File-First)..."

# 1. Verifica ambiente
if [ ! -d ".venv" ]; then
    echo "📦 Creazione ambiente virtuale..."
    python3 -m venv .venv
fi

echo "📥 Installazione dipendenze..."
.venv/bin/pip install -r requirements.txt

# 2. Creazione struttura cartelle
echo "📂 Creazione struttura directory..."
mkdir -p knowledge
mkdir -p data
mkdir -p logs

# 3. Configurazione .env
if [ ! -f ".env" ]; then
    echo "📝 Creazione file .env (ricordati di popolarlo!)..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        echo "OPENAI_API_KEY=your_key_here" > .env
    fi
fi

# 4. Cold Boot (Idratazione)
echo "🧠 Avvio Cold Boot (indicizzazione file esistenti)..."
export PYTHONPATH=.
.venv/bin/python3 workers/file_watcher.py --once

echo ""
echo "✅ Configurazione completata con successo!"
echo "--------------------------------------------------"
echo "Prossimi passi:"
echo "1. Modifica il file .env con le tue chiavi API."
echo "2. Carica i tuoi file .md nella cartella 'knowledge/'."
echo "3. Avvia il sistema con: ./scripts/start.sh"
echo "--------------------------------------------------"
