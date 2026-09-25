#!/bin/bash
# Nightly git bundle of the knowledge snapshot repo, for off-site copies.
# The NAS pulls bundles from BUNDLE_DIR (read-only, via rrsync as backup-nas).
# Retention: every bundle for 30 days, plus the first of each month for a year.
set -euo pipefail

KNOWLEDGE_DIR="${KNOWLEDGE_DIR:-/srv/mnemosyne-gb/knowledge}"
BUNDLE_DIR="${BUNDLE_DIR:-/var/backups/mnemosyne}"
DAY="$(date +%F)"
FINAL="$BUNDLE_DIR/mnemosyne-$DAY.bundle"
TMP="$BUNDLE_DIR/.mnemosyne-$DAY.bundle.tmp"

git -C "$KNOWLEDGE_DIR" bundle create "$TMP" --all 2>/dev/null
git -C "$KNOWLEDGE_DIR" bundle verify -q "$TMP" >/dev/null 2>&1
mv -f "$TMP" "$FINAL"
chmod 644 "$FINAL"

now=$(date +%s)
for f in "$BUNDLE_DIR"/mnemosyne-*.bundle; do
    d="$(basename "$f" .bundle)"; d="${d#mnemosyne-}"
    age=$(( (now - $(date -d "$d" +%s)) / 86400 ))
    if (( age > 365 )) || { (( age > 30 )) && [[ "${d:8:2}" != "01" ]]; }; then
        rm -f "$f"
    fi
done

( cd "$BUNDLE_DIR" && sha256sum mnemosyne-*.bundle > SHA256SUMS && chmod 644 SHA256SUMS )
echo "knowledge_bundle: $(basename "$FINAL") $(du -h "$FINAL" | cut -f1), $(ls "$BUNDLE_DIR"/mnemosyne-*.bundle | wc -l) bundle conservati"
