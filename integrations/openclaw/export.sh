#!/bin/bash
source "$(dirname "$0")/config.sh"

scopes=${1:-"Public"}
limit=${2:-5000}

curl -s -X GET "${MNEMOSYNE_HOST}/graph/export?scopes=${scopes}&limit=${limit}" \
     -H "X-API-Key: ${MNEMOSYNE_KEY}" > export.json

echo "Graph slice exported to $(pwd)/export.json"
