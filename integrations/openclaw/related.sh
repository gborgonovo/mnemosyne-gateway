#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ]; then
    echo "Usage: $0 <node_name> [scopes]"
    exit 1
fi
node_name=$(urlencode "$1")
scopes=${2:-"Public"}

curl -s -X GET "${MNEMOSYNE_HOST}/nodes/${node_name}/neighbors?scopes=${scopes}" \
     -H "X-API-Key: ${MNEMOSYNE_KEY}" | jq . || curl -s -X GET "${MNEMOSYNE_HOST}/nodes/${node_name}/neighbors?scopes=${scopes}" -H "X-API-Key: ${MNEMOSYNE_KEY}"
