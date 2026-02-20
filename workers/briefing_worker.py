import sys
import os
import yaml
import logging
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.plugin_base import PluginBase
from butler.initiative import InitiativeEngine
from core.graph_manager import GraphManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BriefingWorker")

class BriefingWorker(PluginBase):
    def __init__(self, config):
        gateway_host = config.get("gateway", {}).get("host", "localhost")
        gateway_port = config.get("gateway", {}).get("port", 4001)
        
        super().__init__(
            name="Briefing_Worker",
            gateway_url=f"http://{gateway_host}:{gateway_port}",
            host="localhost",
            port=5002,
            capabilities=["NODE_ENERGIZED", "GRAPH_UPDATE"]
        )
        
        self.gm = GraphManager(
            config['graph']['uri'], 
            config['graph']['user'], 
            config['graph']['password']
        )
        self.ie = InitiativeEngine(self.gm, config=config)
        self._setup_handlers()

    def _setup_handlers(self):
        @self.on_event("NODE_ENERGIZED")
        def handle_peak(payload, scope):
            node_name = payload.get("name")
            level = payload.get("level")
            logger.info(f"NODE_ENERGIZED received for {node_name} (level {level:.2f})")
            
            # Generate new initiatives for this context
            # (In a real scenario, this might push a notification to the user)
            initiatives = self.ie.generate_initiatives(scopes=scope)
            if initiatives:
                logger.info(f"Generated {len(initiatives)} initiatives for scope {scope}")
                self.rpc_publish("INITIATIVE_READY", {
                    "initiatives": initiatives,
                    "focus": node_name
                }, scope=scope)

if __name__ == "__main__":
    def load_config():
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    config = load_config()
    worker = BriefingWorker(config)
    worker.run()
