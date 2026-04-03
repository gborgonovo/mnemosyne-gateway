#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ]; then
    echo "Usage: $0 '<json_payload>' [scopes] [limit]"
    echo "Example: $0 '{\"type\": \"Task\", \"status\": \"todo\"}' Public 10"
    exit 1
fi

payload="$1"
scopes=${2:-"Public"}
limit=${3:-50}

curl -s -X POST "${MNEMOSYNE_HOST}/search/advanced?scopes=${scopes}&limit=${limit}" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: ${MNEMOSYNE_KEY}" \
     -d "$payload" | jq . || curl -s -X POST "${MNEMOSYNE_HOST}/search/advanced?scopes=${scopes}&limit=${limit}" -H "Content-Type: application/json" -H "X-API-Key: ${MNEMOSYNE_KEY}" -d "$payload"
