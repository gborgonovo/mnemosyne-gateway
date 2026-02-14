#!/bin/bash
source "$(dirname "$0")/config.sh"

curl -s "${MNEMOSYNE_HOST}/history" | jq . || curl -s "${MNEMOSYNE_HOST}/history"
