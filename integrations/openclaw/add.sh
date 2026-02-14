#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ]; then
    echo "Usage: $0 <content>"
    exit 1
fi

curl -s -X POST "${MNEMOSYNE_HOST}/add" \
     -H "Content-Type: application/json" \
     -d "{\"content\": \"$1\"}" | jq . || curl -s -X POST "${MNEMOSYNE_HOST}/add" -H "Content-Type: application/json" -d "{\"content\": \"$1\"}"
