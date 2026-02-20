#!/bin/bash

# Configuration for Mnemosyne HTTP Bridge
# When execution is from within a Docker container, 'host.docker.internal' usually resolves to the host machine.
# If that fails, tries the default gateway IP.

MNEMOSYNE_HOST="http://host.docker.internal:4001"

# Check if we can reach the server at host.docker.internal
if ! curl -s --connect-timeout 1 "http://host.docker.internal:4001/" > /dev/null; then
    # If not, try localhost (for host-local testing)
    if curl -s --connect-timeout 1 "http://localhost:4001/" > /dev/null; then
        MNEMOSYNE_HOST="http://localhost:4001"
    else
        # Try to guess the host IP (often the gateway)
        GATEWAY_IP=$(ip route show | grep default | awk '{print $3}')
        if [ -n "$GATEWAY_IP" ]; then
            MNEMOSYNE_HOST="http://${GATEWAY_IP}:4001"
        fi
    fi
fi

# Function to URL encode strings
urlencode() {
  local string="$1"
  local strlen=${#string}
  local encoded=""
  local pos c o

  for (( pos=0 ; pos<strlen ; pos++ )); do
     c=${string:$pos:1}
     case "$c" in
        [-_.~a-zA-Z0-9] ) o="${c}" ;;
        * )               printf -v o '%%%02x' "'$c"
     esac
     encoded+="${o}"
  done
  echo "${encoded}"
}
