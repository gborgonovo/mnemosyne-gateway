#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ]; then
    echo "Usage: $0 <content>"
    exit 1
fi

scope=${2:-"Public"}
curl -s -X POST "${MNEMOSYNE_HOST}/add?scope=${scope}" \
     -H "Content-Type: application/json" \
     -d "{\"content\": \"$1\"}" | jq . || curl -s -X POST "${MNEMOSYNE_HOST}/add?scope=${scope}" -H "Content-Type: application/json" -d "{\"content\": \"$1\"}"
