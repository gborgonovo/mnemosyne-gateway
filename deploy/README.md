# Deploy notes

Production runs on the VPS (`/srv/mnemosyne-gb`), started by systemd. Deploy is
git-based: `git pull` on the VPS, then restart. Never hand-edit the checked-out
tree on the server.

Units in this folder:
- `mnemosyne.service` — the gateway (FastAPI + MCP), port 4001.
- `mnemosyne-knowledge-backup.{service,timer}` — daily git snapshot of `knowledge/`.

## Run as `oste`, not root (one-time migration)

Both services now declare `User=oste` / `Group=oste`. The gateway must NOT run as
root: it shares `knowledge/` with Syncthing (which runs as `oste`), and when the
gateway ran as root every atomic rewrite left the file `root:root`, so Syncthing
could no longer read/hash it and changes stopped propagating silently. Running as
`oste` makes the gateway and Syncthing share the same owner.

This requires `oste` to own the whole tree. Do it once, in this order:

```bash
# 1. Stop the gateway (release the KuzuDB single-writer lock before chowning data/).
sudo systemctl stop mnemosyne

# 2. Give the whole tree to oste: data/ (Kuzu/Chroma + their locks), knowledge/
#    (+ its .git), .venv, .env, config/, logs/, everything.
sudo chown -R oste:oste /srv/mnemosyne-gb

# 3. (If not already done as the one-time unblock) heal any .md left at 0600 by
#    the old root writer, so Syncthing can read them. The atomic_write fix keeps
#    new writes readable; this fixes the historical ones.
sudo -u oste find /srv/mnemosyne-gb/knowledge -type f -name '*.md' -exec chmod 0644 {} +

# 4. Install the updated units. Check first how they're installed:
sudo systemctl cat mnemosyne | head -1        # shows the unit file path
#   - If /etc/systemd/system/mnemosyne.service is a SYMLINK to this repo: nothing
#     to copy, the git pull already updated it.
#   - If it's a COPY, refresh both units:
sudo cp deploy/mnemosyne.service deploy/mnemosyne-knowledge-backup.service \
        /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Start the gateway.
sudo systemctl start mnemosyne
```

### Verify

```bash
# Runs as oste (not root):
systemctl show -p MainPID --value mnemosyne | xargs -I{} ps -o user=,pid=,cmd= -p {}

# Started cleanly, no "Permission denied" opening KuzuDB / reading .env:
journalctl -u mnemosyne -n 60 --no-pager

# API up, and a fresh write lands as oste:
curl -s http://localhost:4001/status | python3 -m json.tool | head
# then create/edit a node via MCP or REST and:
ls -l /srv/mnemosyne-gb/knowledge/<the-file>.md   # expect oste:oste, mode 644
```

### Gotchas

- **`.env` must be oste-readable.** The unit loads it with `EnvironmentFile=-`,
  which *silently ignores* an unreadable file — the gateway would then start
  without `MNEMOSYNE_API_KEY` etc. and (with `auth_required: true`) refuse to
  start, or Alfred's cron would break. Step 2 chowns it; keep its mode 600.
- **Backup runs as oste too.** Once `oste` owns `knowledge/.git`, a root-run
  `git` aborts with "dubious ownership"; that's why the backup unit also has
  `User=oste`. Test it: `sudo systemctl start mnemosyne-knowledge-backup && journalctl -u mnemosyne-knowledge-backup -n 20 --no-pager`.
- **Manual re-embed** (the note in `mnemosyne.service`) must be run as
  `sudo -u oste`, never root, or it recreates root-owned files and reopens the bug.
- **Rollback**: if the gateway won't start as oste, `sudo systemctl edit mnemosyne`
  and add `[Service]\nUser=root\nGroup=root` as a drop-in (or restore the old unit),
  `daemon-reload`, `start`, then investigate the journal (usually a path still
  owned by root that step 2 missed).

## Related

- `atomic_write` (core/utils.py) guarantees group/other-read on every write — a
  safety net that stays inert once the gateway runs as oste.
- Thermal-state backup writes `knowledge/_system/thermal_state.json`; add
  `_system/` to Syncthing's `.stignore` on the VPS (see the file-watcher / thermal
  backup notes).
