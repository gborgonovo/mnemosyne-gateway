#!/bin/bash
# restart.sh - Riavvia Mnemosyne e i Worker verificando lo stato

# Spostati nella root del progetto
cd "$(dirname "$0")/.."

echo "♻️  Riavvio di Mnemosyne in corso..."

# 1. Ferma tutto
./scripts/stop.sh

# Breve attesa per assicurarsi che le porte siano libere
sleep 1

# 2. Avvia tutto
./scripts/start.sh

echo "⏳ In attesa che il Gateway sia pronto..."
# Attesa di 3 secondi per l'inizializzazione del gateway
sleep 5

# Estrai la porta dalla configurazione (default 4001)
PYTHON_CMD="python3"
if [ -f ".venv/bin/python3" ]; then PYTHON_CMD=".venv/bin/python3"; fi
PORT=$($PYTHON_CMD -c "import yaml; print(yaml.safe_load(open('config/settings.yaml'))['gateway']['port'])" 2>/dev/null || echo 4001)

# 3. Verifica dello stato
echo "🔍 Verifica dello stato sulla porta $PORT..."
if curl -s -f http://localhost:$PORT/status > /dev/null; then
    curl -s http://localhost:$PORT/status | $PYTHON_CMD -m json.tool
    echo "✅ Sistema riavviato correttamente!"
else
    echo "❌ Errore nella verifica del Gateway sulla porta $PORT."
    echo "Controlla i log con: tail -n 20 logs/gateway.log"
fi

echo ""
echo "🚀 Operazione di restart completata."
