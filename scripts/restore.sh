#!/bin/bash
# restore.sh - Ripristina il Connectome (Grafo) da un backup esistente

# Root directory
cd "$(dirname "$0")/.."

BACKUP_DIR="data/backups"

# Se non viene passato un file, mostra la lista e usa l'ultimo (latest.json)
if [ -z "$1" ]; then
    echo "❓ Nessun file specificato. Backup disponibili in $BACKUP_DIR:"
    if [ -d "$BACKUP_DIR" ]; then 
        ls -1 "$BACKUP_DIR"/*.json | sort -r
    else
        echo "❌ Nessun backup trovato in $BACKUP_DIR."
        exit 1
    fi
    
    LATEST="$BACKUP_DIR/latest.json"
    if [ -f "$LATEST" ]; then
        FILE="$LATEST"
        echo ""
        echo "🔄 Ripristino automatico dell'ultimo backup disponibile: $FILE"
    else
        echo "❌ Nessun backup trovato. Specifica un file: ./scripts/restore.sh <percorso_file>"
        exit 1
    fi
else
    FILE="$1"
fi

if [ ! -f "$FILE" ]; then
    echo "❌ File non trovato: $FILE"
    exit 1
fi

echo "⚠️  ATTENZIONE: Questo ripristino sovrascriverà i nodi esistenti in conflitto di nomi."
read -p "Vuoi procedere? [s/N]: " confirm
if [[ $confirm == [sS] ]]; then
    echo "📥 Inizio ripristino da $FILE..."
    
    # Usa il venv se presente, altrimenti python3 di sistema
    PYTHON_CMD="python3"
    if [ -f ".venv/bin/python3" ]; then
        PYTHON_CMD=".venv/bin/python3"
    fi
    
    $PYTHON_CMD scripts/manage_db.py restore --file "$FILE"
    
    if [ $? -eq 0 ]; then
        echo "✅ Ripristino completato correttamente!"
    else
        echo "❌ Errore durante il ripristino!"
    fi
else
    echo "🚫 Operazione annullata."
fi
