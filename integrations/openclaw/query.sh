#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ]; then
    echo "Usage: $0 <query>"
    exit 1
fi

encoded_q=$(urlencode "$1")
scopes=${2:-"Public"}
curl -s "${MNEMOSYNE_HOST}/search?q=${encoded_q}&scopes=${scopes}" -H "X-API-Key: ${MNEMOSYNE_KEY}" | jq . || curl -s "${MNEMOSYNE_HOST}/search?q=${encoded_q}&scopes=${scopes}" -H "X-API-Key: ${MNEMOSYNE_KEY}"
