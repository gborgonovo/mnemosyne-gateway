#!/bin/bash
source "$(dirname "$0")/config.sh"

scopes=${1:-"Public"}
curl -s -X GET "${MNEMOSYNE_HOST}/graph/schema?scopes=${scopes}" \
     -H "X-API-Key: ${MNEMOSYNE_KEY}" | jq . || curl -s -X GET "${MNEMOSYNE_HOST}/graph/schema?scopes=${scopes}" -H "X-API-Key: ${MNEMOSYNE_KEY}"
