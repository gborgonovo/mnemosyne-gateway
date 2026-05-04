#!/bin/bash
# restore.sh - Restore the Connectome (Graph) from an existing backup

cd "$(dirname "$0")/.."

BACKUP_DIR="data/backups"

if [ -z "$1" ]; then
    echo "❓ No file specified. Available backups in $BACKUP_DIR:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -1 "$BACKUP_DIR"/*.json | sort -r
    else
        echo "❌ No backups found in $BACKUP_DIR."
        exit 1
    fi

    LATEST="$BACKUP_DIR/latest.json"
    if [ -f "$LATEST" ]; then
        FILE="$LATEST"
        echo ""
        echo "🔄 Auto-restoring from latest available backup: $FILE"
    else
        echo "❌ No backup found. Specify a file: ./scripts/restore.sh <file_path>"
        exit 1
    fi
else
    FILE="$1"
fi

if [ ! -f "$FILE" ]; then
    echo "❌ File not found: $FILE"
    exit 1
fi

echo "⚠️  WARNING: This restore will overwrite existing nodes with conflicting names."
read -p "Proceed? [y/N]: " confirm
if [[ $confirm == [yY] ]]; then
    echo "📥 Starting restore from $FILE..."

    PYTHON_CMD="python3"
    if [ -f ".venv/bin/python3" ]; then
        PYTHON_CMD=".venv/bin/python3"
    fi

    $PYTHON_CMD scripts/manage_db.py restore --file "$FILE"

    if [ $? -eq 0 ]; then
        echo "✅ Restore completed successfully!"
    else
        echo "❌ Error during restore!"
    fi
else
    echo "🚫 Operation cancelled."
fi
