#!/bin/bash
source "$(dirname "$0")/config.sh"

curl -s "${MNEMOSYNE_HOST}/briefing" | jq . || curl -s "${MNEMOSYNE_HOST}/briefing"
