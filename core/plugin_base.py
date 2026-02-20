import logging
import requests
import threading
import time
from fastapi import FastAPI, Request
from typing import List, Dict, Any, Callable
import uvicorn

logger = logging.getLogger(__name__)

class PluginBase:
    """
    Standard base class for Mnemosyne Plugins.
    Provides automated registration (Handshake) and an event listener.
    """
    def __init__(self, name: str, gateway_url: str, host: str, port: int, capabilities: List[str] = None):
        self.name = name
        self.gateway_url = gateway_url.rstrip('/')
        self.host = host
        self.port = port
        self.capabilities = capabilities or []
        self.plugin_id = None
        self.app = FastAPI(title=f"Mnemosyne Plugin: {name}")
        self._setup_routes()
        self._handlers: Dict[str, List[Callable]] = {}

    def _setup_routes(self):
        @self.app.post("/event")
        async def receive_event(request: Request):
            data = await request.json()
            event_type = data.get("event_type")
            payload = data.get("payload")
            scope = data.get("scope")
            
            # Execute handlers
            if event_type in self._handlers:
                for handler in self._handlers[event_type]:
                    try:
                        handler(payload, scope)
                    except Exception as e:
                        logger.error(f"Error in plugin handler for {event_type}: {e}")
            return {"status": "ok"}

    def on_event(self, event_type: str):
        """Decorator for registering event handlers."""
        def decorator(func: Callable):
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func
        return decorator

    def register(self):
        """Perform Handshake with the Gateway."""
        url = f"{self.gateway_url}/register"
        payload = {
            "name": self.name,
            "url": f"http://{self.host}:{self.port}",
            "capabilities": self.capabilities
        }
        
        max_retries = 10
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=5)
                response.raise_for_status()
                data = response.json()
                self.plugin_id = data.get("plugin_id")
                logger.info(f"Successfully registered as {self.name} (ID: {self.plugin_id})")
                return
            except Exception as e:
                logger.warning(f"Registration attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in 3s...")
                time.sleep(3)
                
        logger.error(f"Failed to register at gateway after {max_retries} attempts.")

    def run(self):
        """Start the plugin's HTTP server."""
        # Registration in a separate thread to not block startup
        threading.Thread(target=self._delayed_registration, daemon=True).start()
        uvicorn.run(self.app, host=self.host, port=self.port)

    def _delayed_registration(self):
        time.sleep(1) # Wait for server to start
        self.register()

    def rpc_publish(self, event_type: str, payload: Dict[str, Any], scope: List[str] = None):
        """Send an event back to the Core via the Gateway."""
        url = f"{self.gateway_url}/rpc"
        event = {
            "event_type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scope": scope or ["Public"],
            "payload": payload
        }
        try:
            requests.post(url, json=event, timeout=5)
        except Exception as e:
            logger.error(f"Failed to publish RPC event: {e}")
