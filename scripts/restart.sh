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

# 3. Verifica dello stato
echo "🔍 Verifica dello stato..."
if curl -s -f http://localhost:4001/status > /dev/null; then
    curl -s http://localhost:4001/status | python3 -m json.tool
    echo "✅ Sistema riavviato correttamente!"
else
    echo "❌ Errore nella verifica del Gateway. Il servizio potrebbe essere ancora in fase di avvio o aver riscontrato un problema."
    echo "Controlla i log con: tail -n 20 logs/gateway.log"
fi

echo ""
echo "🚀 Operazione di restart completata."
