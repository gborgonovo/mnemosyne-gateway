#!/bin/bash
# backup.sh - Create a timestamped backup of the Connectome (Graph)

cd "$(dirname "$0")/.."

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="data/backups"
BACKUP_FILE="$BACKUP_DIR/connectome_$TIMESTAMP.json"

mkdir -p "$BACKUP_DIR"

echo "📦 Starting Mnemosyne backup..."

PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then
    PYTHON_CMD=".venv/bin/python3"
fi

$PYTHON_CMD scripts/manage_db.py backup --file "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Backup completed successfully."
    echo "📄 File: $BACKUP_FILE"
    ln -sf "connectome_$TIMESTAMP.json" "$BACKUP_DIR/latest.json"
    echo "🔗 Symbolic link created: $BACKUP_DIR/latest.json"
else
    echo "❌ Error during backup!"
    exit 1
fi
