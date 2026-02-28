import sys
import os
import yaml
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.plugin_base import PluginBase
from butler.llm import get_llm_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMWorker")

class LLMWorker(PluginBase):
    def __init__(self, config):
        gateway_host = config.get("gateway", {}).get("host", "localhost")
        gateway_port = config.get("gateway", {}).get("port", 4001)
        
        super().__init__(
            name="LLM_Worker",
            gateway_url=f"http://{gateway_host}:{gateway_port}",
            host="localhost",
            port=5001,
            capabilities=["REQ_ENRICHMENT"]
        )
        butler_config = config.get("llm", {}).get("butler", config.get("llm", {}))
        self.llm = get_llm_provider(butler_config, root_config=config)
        self._setup_handlers()

    def _setup_handlers(self):
        @self.on_event("REQ_ENRICHMENT")
        def handle_enrichment(payload, scope):
            text = payload.get("text")
            obs_name = payload.get("obs_name")
            context = payload.get("context_nodes", [])
            logger.info(f"Processing enrichment request for {obs_name}: {text[:50]}...")
            
            entities = self.llm.extract_entities(text, context_nodes=context)
            
            # Send result back via RPC
            self.rpc_publish("ENRICHMENT_RESULT", {
                "obs_name": obs_name,
                "entities": entities
            }, scope=scope)

if __name__ == "__main__":
    def load_config():
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    config = load_config()
    worker = LLMWorker(config)
    worker.run()
