#!/usr/bin/env python3
"""
Backfill LLM enrichment for knowledge nodes that have never been enriched,
or whose content changed after the last enrichment (mtime > enriched_at).

Usage:
    python3 scripts/backfill_enrichment.py [--dry-run] [--force]

Options:
    --dry-run   List files that would be enriched without calling the LLM.
    --force     Re-enrich all eligible files, ignoring enriched_at.
"""
import os
import sys
import yaml
import re
import datetime
import argparse
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils import normalize_node_name
from butler.llm import get_llm_provider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - backfill - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, 'knowledge')
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'settings.yaml')


def parse_markdown(filepath):
    frontmatter, body = {}, ""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        m = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        if m:
            frontmatter = yaml.safe_load(m.group(1)) or {}
            body = m.group(2).strip()
        else:
            body = content.strip()
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None, None
    return frontmatter, body


def write_frontmatter(filepath, frontmatter, body):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
        f.write("---\n\n")
        f.write(body)


def needs_enrichment(filepath, frontmatter, force=False):
    if force:
        return True
    node_type = frontmatter.get('type', 'Node')
    if node_type == 'Observation':
        return False
    enriched_at = frontmatter.get('enriched_at')
    if enriched_at is None:
        return True
    if not isinstance(enriched_at, datetime.datetime):
        try:
            enriched_at = datetime.datetime.fromisoformat(str(enriched_at))
        except ValueError:
            return True
    file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
    return (file_mtime - enriched_at).total_seconds() > 3600


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='List eligible files without enriching')
    parser.add_argument('--force', action='store_true', help='Re-enrich all files ignoring enriched_at')
    args = parser.parse_args()

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    if not args.dry_run:
        butler_config = config.get('llm', {}).get('butler', {})
        llm = get_llm_provider(butler_config, root_config=config)
        logger.info(f"LLM provider: {llm.get_info()}")

    eligible, enriched, skipped, errors = [], 0, 0, 0
    all_node_names = set()

    for root, _, files in os.walk(KNOWLEDGE_DIR):
        for fname in sorted(files):
            if not fname.endswith('.md') or fname.startswith('_'):
                continue
            all_node_names.add(normalize_node_name(os.path.splitext(fname)[0]))

    for root, _, files in os.walk(KNOWLEDGE_DIR):
        for fname in sorted(files):
            if not fname.endswith('.md') or fname.startswith('_'):
                continue
            filepath = os.path.join(root, fname)
            frontmatter, body = parse_markdown(filepath)
            if frontmatter is None or not body or len(body) <= 150:
                skipped += 1
                continue
            if not needs_enrichment(filepath, frontmatter, force=args.force):
                skipped += 1
                continue
            eligible.append((filepath, fname, frontmatter, body))

    logger.info(f"Found {len(eligible)} files to enrich, {skipped} skipped.")

    if args.dry_run:
        for filepath, fname, _, _ in eligible:
            print(f"  would enrich: {os.path.relpath(filepath, BASE_DIR)}")
        return

    for filepath, fname, frontmatter, body in eligible:
        raw_name = os.path.splitext(fname)[0]
        norm_name = normalize_node_name(raw_name)
        try:
            _, relationships = llm.extract_entities(body, context_nodes=sorted(all_node_names), current_node=raw_name)
            llm_relations = []
            for rel in relationships:
                src = normalize_node_name(str(rel.get('source', '')))
                tgt = normalize_node_name(str(rel.get('target', '')))
                if src == norm_name and tgt in all_node_names and tgt != norm_name:
                    llm_relations.append({
                        'target': rel.get('target', ''),
                        'type': str(rel.get('type', 'RELATED_TO')).upper(),
                        'source': 'llm',
                    })
            # Preserve user-authored relations (no source or source != llm)
            existing = frontmatter.get('relations') or []
            user_relations = [r for r in existing if r.get('source') != 'llm']
            frontmatter['relations'] = user_relations + llm_relations
            frontmatter['enriched_at'] = datetime.datetime.now()
            write_frontmatter(filepath, frontmatter, body)
            logger.info(f"✓ {os.path.relpath(filepath, BASE_DIR)} → {len(llm_relations)} llm + {len(user_relations)} user relations")
            enriched += 1
        except Exception as e:
            logger.error(f"✗ {fname}: {e}")
            errors += 1

    logger.info(f"Done. Enriched: {enriched}, errors: {errors}.")
    if enriched > 0:
        logger.info("The file watcher will sync new relations to KuzuDB automatically.")


if __name__ == '__main__':
    main()
