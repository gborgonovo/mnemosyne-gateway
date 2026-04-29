#!/bin/bash
# Semplice wrapper per interrogare Mnemosyne via HTTP

QUERY=$1
if [ -z "$QUERY" ]; then
    echo "Usage: ./query.sh \"tua domanda\""
    exit 1
fi

curl -s "http://localhost:4002/search?q=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))")" | jq .
