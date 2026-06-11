#!/bin/bash
# Daily git snapshot of the Mnemosyne knowledge base.
# Meant to be run by the mnemosyne-knowledge-backup.timer systemd unit.
# Git must be initialized in KNOWLEDGE_DIR before first run (see deploy/README).

set -euo pipefail

KNOWLEDGE_DIR="${KNOWLEDGE_DIR:-/srv/mnemosyne-gb/knowledge}"

cd "$KNOWLEDGE_DIR"

# Nothing to commit — exit cleanly (timer considers this a success)
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "knowledge_backup: nothing changed, skipping commit"
    exit 0
fi

git add -A
git commit \
    --author="Mnemosyne <mnemosyne@borgonovo.org>" \
    -m "snapshot: $(date '+%Y-%m-%d %H:%M')"

echo "knowledge_backup: committed snapshot $(git rev-parse --short HEAD)"
