"""
Plugin Runner — executes Mnemosyne Alfred plugins.

Usage:
    python3 workers/plugin_runner.py --plugin morning_briefing

Each plugin is a YAML file in plugins/ that declares:
  - context: which gateway endpoints to query
  - delivery: which adapter to use (smtp, ntfy, …)
  - prompt: the LLM template to compose the message
"""
import sys
import os
import yaml
import argparse
import logging
import requests
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / '.env')

from butler.llm import get_llm_provider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("PluginRunner")

ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    with open(ROOT / 'config' / 'settings.yaml') as f:
        return yaml.safe_load(f)


def load_plugin(name: str) -> dict:
    path = ROOT / 'plugins' / f'{name}.yaml'
    if not path.exists():
        raise FileNotFoundError(f"Plugin not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def gather_context(plugin: dict, gateway_url: str, api_key: str = None) -> dict:
    headers = {"X-API-Key": api_key} if api_key else {}
    context = {}
    for endpoint in plugin.get('context', {}).get('endpoints', []):
        path   = endpoint if isinstance(endpoint, str) else endpoint['path']
        params = {} if isinstance(endpoint, str) else endpoint.get('params', {})
        url = gateway_url.rstrip('/') + path
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            context[path] = resp.json()
            logger.info(f"Fetched context from {path}")
        except Exception as e:
            logger.warning(f"Could not fetch {path}: {e}")
            context[path] = {}
    return context


def compose_message(plugin: dict, context: dict, llm) -> str:
    template = plugin.get('prompt', 'Summarize the following context:\n{context}')
    today = date.today().strftime('%A %d %B %Y')
    context_text = yaml.dump(context, allow_unicode=True, default_flow_style=False)
    prompt = template.format(date=today, context=context_text)
    try:
        return llm.generate(prompt)
    except Exception as e:
        logger.warning(f"LLM composition failed ({e}), sending raw context")
        return f"Alfred — {today}\n\n{context_text}"


def deliver(plugin: dict, message: str):
    delivery = plugin.get('delivery', {})
    tool = delivery.get('tool')

    if tool == 'smtp':
        from adapters.smtp import send_email
        subject   = delivery.get('subject', plugin.get('name', 'Alfred'))
        recipient = delivery.get('recipient') or os.environ.get('ALFRED_EMAIL_TO')
        send_email(subject=subject, body=message, to=recipient)
        logger.info(f"Email sent to {recipient}")

    elif tool == 'ntfy':
        from adapters.ntfy import send_notification
        topic   = delivery.get('topic') or os.environ.get('NTFY_TOPIC')
        title   = delivery.get('title', plugin.get('name', 'Alfred'))
        send_notification(topic=topic, title=title, body=message)
        logger.info(f"Notification sent to ntfy topic '{topic}'")

    else:
        raise ValueError(f"Unknown delivery tool: '{tool}'. Available: smtp, ntfy")


def _context_is_empty(context: dict) -> bool:
    """Returns True if all list-valued fields across all endpoint responses are empty."""
    for payload in context.values():
        if isinstance(payload, dict):
            if any(isinstance(v, list) and v for v in payload.values()):
                return False
    return True


def run_plugin(name: str):
    config      = load_config()
    plugin      = load_plugin(name)
    gateway_url = os.environ.get('MNEMOSYNE_GATEWAY_URL', 'http://localhost:4001')
    api_key     = os.environ.get('MNEMOSYNE_API_KEY')

    logger.info(f"Running plugin: {name}")
    context = gather_context(plugin, gateway_url, api_key)

    if all(not v for v in context.values()):
        logger.error("All context endpoints failed — check MNEMOSYNE_API_KEY and gateway availability.")
        sys.exit(1)

    if _context_is_empty(context):
        logger.info("Briefing context is empty — nothing to report, skipping delivery.")
        return

    llm     = get_llm_provider(config['llm']['butler'], root_config=config)
    message = compose_message(plugin, context, llm)
    deliver(plugin, message)
    logger.info(f"Plugin '{name}' completed.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run a Mnemosyne Alfred plugin")
    parser.add_argument('--plugin', required=True, help="Plugin name (without .yaml)")
    args = parser.parse_args()
    run_plugin(args.plugin)
