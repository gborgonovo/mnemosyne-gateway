#!/bin/bash
source "$(dirname "$0")/config.sh"

scopes=${1:-"Public"}
curl -s "${MNEMOSYNE_HOST}/briefing?scopes=${scopes}" | jq . || curl -s "${MNEMOSYNE_HOST}/briefing?scopes=${scopes}"
