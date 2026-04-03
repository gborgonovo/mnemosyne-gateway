#!/bin/bash
source "$(dirname "$0")/config.sh"

curl -s "${MNEMOSYNE_HOST}/status" -H "X-API-Key: ${MNEMOSYNE_KEY}" | jq . || curl -s "${MNEMOSYNE_HOST}/status" -H "X-API-Key: ${MNEMOSYNE_KEY}"
