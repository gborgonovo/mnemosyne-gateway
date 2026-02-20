#!/bin/bash
source "$(dirname "$0")/config.sh"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <node_name> <to_scope>"
    exit 1
fi

curl -s -X POST "${MNEMOSYNE_HOST}/share" \
     -H "Content-Type: application/json" \
     -d "{\"node_name\": \"$1\", \"to_scope\": \"$2\"}" | jq . || curl -s -X POST "${MNEMOSYNE_HOST}/share" -H "Content-Type: application/json" -d "{\"node_name\": \"$1\", \"to_scope\": \"$2\"}"
