#!/bin/bash
# backup.sh - Crea un backup del Connectome (Grafo) con timestamp

# Root directory
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="data/backups"
BACKUP_FILE="$BACKUP_DIR/connectome_$TIMESTAMP.json"

# Crea la cartella se non esiste
mkdir -p "$BACKUP_DIR"

echo "📦 Inizio backup di Mnemosyne..."

# Usa il venv se presente, altrimenti python3 di sistema
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then
    PYTHON_CMD=".venv/bin/python3"
fi

$PYTHON_CMD scripts/manage_db.py backup --file "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Backup completato con successo."
    echo "📄 File: $BACKUP_FILE"
    # Crea un link simbolico all'ultimo backup per comodità di restore
    ln -sf "connectome_$TIMESTAMP.json" "$BACKUP_DIR/latest.json"
    echo "🔗 Creato link simbolico: $BACKUP_DIR/latest.json"
else
    echo "❌ Errore durante il backup!"
    exit 1
fi
