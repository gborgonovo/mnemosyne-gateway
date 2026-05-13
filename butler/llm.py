from abc import ABC, abstractmethod
import random
import logging
import requests
import json
import os
from openai import OpenAI

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract Base Class for LLM interactions."""
    
    @abstractmethod
    def generate(self, prompt: str, context: dict = None, timeout: int = None) -> str:
        pass

    @abstractmethod
    def generate_response(self, user_text: str, proactive_context: str = "", impact_context: str = "", semantic_context: str = "") -> str:
        """Generates a response in The Butler's persona."""
        pass

    @abstractmethod
    def extract_entities(self, text: str, context_nodes: list[str] = None, current_node: str = None) -> tuple[list[dict], list[dict]]:
        """Extracts entities and relationships from text. Returns tuple of (entities, relationships)."""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generates an embedding vector for the given text."""
        pass

    @abstractmethod
    def compare_entities(self, entity_a: str, entity_b: str) -> bool:
        """Determines if two entity names refer to the same semantic concept."""
        pass

    @abstractmethod
    def get_info(self) -> dict:
        """Returns provider metadata for status checks."""
        pass

class MockLLM(LLMProvider):
    """A dummy LLM for development on limited hardware."""
    
    def generate(self, prompt: str, context: dict = None, timeout: int = None) -> str:
        logger.info(f"MOCK LLM GENERATION\nPrompt: {prompt[:50]}...")
        responses = [
            "This is a mock response from Mnemosyne (Dev Mode).",
            "I noticed you are working on the Mnemosyne project. How is the graph structure coming along?",
            "Thinking about your request... (Simulated Latency)... Done.",
            "Interesting connection! This reminds me of the 'Project B&B' node."
        ]
        return random.choice(responses)

    def generate_response(self, user_text: str, proactive_context: str = "", impact_context: str = "", semantic_context: str = "") -> str:
        return f"Signore, ho ricevuto il suo messaggio: '{user_text}'. {proactive_context} {impact_context} {semantic_context}".strip()

    def extract_entities(self, text: str, context_nodes: list[str] = None, current_node: str = None) -> tuple[list[dict], list[dict]]:
        logger.info(f"MOCK LLM EXTRACTION\nText: {text[:50]}...")
        words = text.split()
        entities = []
        for w in words:
            if w[0].isupper() and len(w) > 2:
                entities.append({"name": w.strip(".,;:"), "type": "Topic"})
        return entities, []

    def embed(self, text: str) -> list[float]:
        # Return a deterministic "mock" vector based on text length
        return [float(len(text))] * 16

    def compare_entities(self, entity_a: str, entity_b: str) -> bool:
        # Mock: just check if they are very similar or lowercase matches
        return entity_a.lower() == entity_b.lower()

    def get_info(self) -> dict:
        return {"mode": "mock", "model": "internal-mock"}

class OpenAILLM(LLMProvider):
    """Implementation using OpenAI-compatible API."""
    
    def __init__(self, api_key: str, model: str, base_url: str = None, config: dict = None):
        # If base_url is provided, use it (allows DeepSeek, local vLLM, etc.)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.config = config or {}

    def generate(self, prompt: str, context: dict = None, timeout: int = None) -> str:
        # OpenAI SDK handles timeouts via its client config or per-request
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout
        )
        return response.choices[0].message.content

    def generate_response(self, user_text: str, proactive_context: str = "", impact_context: str = "", semantic_context: str = "") -> str:
        """
        Generates a response in The Butler's persona, optionally weaving in proactive or impact context.
        """
        # Look for butler prompt in the root config if passed, or use default
        system_prompt = self.config.get("llm", {}).get("prompts", {}).get("butler") or \
                        self.config.get("prompts", {}).get("butler", "You are a helpful assistant.")
        
        full_user_prompt = f"User said: {user_text}\n"
        
        if semantic_context:
            full_user_prompt += f"\n[MNEMOSYNE MEMORY RETRIEVAL (Semantic Context)]:\n{semantic_context}\n(Use this specific knowledge to answer. If the user asks about these entities, use these details.)"

        if proactive_context:
            full_user_prompt += f"\n[PROACTIVE INITIATIVE (Topics to mention if relevant)]:\n{proactive_context}"
        
        if impact_context:
            full_user_prompt += f"\n[SANDBOX SIMULATION (Impact Analysis)]:\n{impact_context}\nExplain to the user how a change in the starting node affects these downstream dependencies."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_user_prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Response generation error: {e}")
            return "I'm sorry, I'm having some difficulty processing your request."

    def extract_entities(self, text: str, context_nodes: list[str] = None, current_node: str = None) -> tuple[list[dict], list[dict]]:
        context_nodes = context_nodes or []
        context_info = ""
        if context_nodes:
            context_info = f"\nKnown nodes already in the graph: {', '.join(context_nodes)}. Prefer these exact names when they match concepts in the text."

        if current_node:
            prompt = f"""You are analyzing a knowledge node named "{current_node}".{context_info}

The text below is the content of this node. Extract its direct relationships to other concepts.

Return a JSON object with:
1. "entities": empty list [] (we only need relations here)
2. "relationships": list of objects, each with:
   - "source": must always be exactly "{current_node}"
   - "target": the related concept name
   - "type": one of BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A

Extract only relationships where "{current_node}" is the subject. Be concrete: prefer specific targets over vague ones. Include 3-8 relationships if the text supports them.

Text: {text}"""
        else:
            prompt = f"""Extract key entities and topics from the following text.{context_info}
Return a JSON object with:
1. "entities": list of objects with 'name', 'type' (Topic, Project, Goal, Task), and 'description'.
2. "relationships": list of objects with 'source', 'target', and 'type' (BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A).

Text: {text}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a specialized knowledge graph extractor. Return only JSON."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            logger.debug(f"LLM Response: {content}")
            data = json.loads(content)

            if isinstance(data, list): return data, []
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            return entities, relationships
        except Exception as e:
            logger.error(f"LLM Extraction error: {e}")
            return [], []

    def embed(self, text: str) -> list[float]:
        try:
            # The model is the one passed to __init__
            response = self.client.embeddings.create(
                input=[text],
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI Embedding error: {e}")
            return []

    def compare_entities(self, entity_a: str, entity_b: str) -> bool:
        prompt = f"Are the concepts '{entity_a}' and '{entity_b}' referring to the same thing in a knowledge graph? Answer only YES or NO."
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a logical reasoner for graph consolidation."},
                          {"role": "user", "content": prompt}]
            )
            return "YES" in response.choices[0].message.content.upper()
        except Exception as e:
            logger.error(f"LLM Comparison error: {e}")
            return False

    def get_info(self) -> dict:
        return {
            "mode": "openai/remote",
            "model": self.model,
            "base_url": str(self.client.base_url)
        }

class OllamaLLM(LLMProvider):
    """Real implementation connecting to Ollama."""
    
    def __init__(self, base_url: str, model: str, config: dict = None):
        self.base_url = base_url
        self.model = model
        self.config = config or {}

    def _call_ollama(self, endpoint: str, data: dict, timeout: int = 30, silent: bool = False) -> dict:
        url = f"{self.base_url.rstrip('/')}/api/{endpoint}"
        try:
            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if not silent:
                logger.error(f"Ollama API error ({url}): {e}")
            raise

    def generate(self, prompt: str, context: dict = None, timeout: int = 30) -> str:
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            res = self._call_ollama("generate", data, timeout=timeout)
            return res.get("response", "")
        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            return "I am sorry, I encountered an error while generating a response."

    def generate_response(self, user_text: str, proactive_context: str = "", impact_context: str = "", semantic_context: str = "") -> str:
        system_prompt = self.config.get("llm", {}).get("prompts", {}).get("butler") or \
                        self.config.get("prompts", {}).get("butler", "You are a helpful assistant.")
        
        full_user_prompt = f"User said: {user_text}\n"
        
        if semantic_context:
            full_user_prompt += f"\n[MNEMOSYNE MEMORY RETRIEVAL (Semantic Context)]:\n{semantic_context}\n(Use this specific knowledge to answer. If the user asks about these entities, use these details.)"

        if proactive_context:
            full_user_prompt += f"\n[PROACTIVE INITIATIVE (Topics to mention if relevant)]:\n{proactive_context}"
        
        if impact_context:
            full_user_prompt += f"\n[SANDBOX SIMULATION (Impact Analysis)]:\n{impact_context}\nExplain to the user how a change in the starting node affects these downstream dependencies."

        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_user_prompt}
            ],
            "stream": False
        }
        try:
            res = self._call_ollama("chat", data)
            return res.get("message", {}).get("content", "I am sorry, I am having trouble thinking right now.")
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return "I'm sorry, I'm having some difficulty processing your local request."

    def extract_entities(self, text: str, context_nodes: list[str] = None, current_node: str = None) -> tuple[list[dict], list[dict]]:
        context_nodes = context_nodes or []
        context_info = ""
        if context_nodes:
            context_info = f"\nKnown nodes already in the graph: {', '.join(context_nodes)}. Prefer these exact names when they match concepts in the text."

        if current_node:
            prompt = f"""You are analyzing a knowledge node named "{current_node}".{context_info}

The text below is the content of this node. Extract its direct relationships to other concepts.

Return a JSON object with:
1. "entities": empty list []
2. "relationships": list of objects, each with:
   - "source": must always be exactly "{current_node}"
   - "target": the related concept name
   - "type": one of BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A

Extract only relationships where "{current_node}" is the subject. Include 3-8 relationships if the text supports them. Return ONLY the JSON object.

Text: {text}"""
        else:
            prompt = f"""Extract key entities and topics from the following text.{context_info}
Return a JSON object with:
1. "entities": list of objects with 'name', 'type' (Topic, Project, Goal, Task), and 'description'.
2. "relationships": list of objects with 'source', 'target', and 'type' (BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A).
Return ONLY the JSON object.

Text: {text}"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        try:
            res = self._call_ollama("generate", payload)
            content = res.get("response", "{}")
            logger.debug(f"Ollama Extraction Response: {content}")
            if not content or content.strip() == "":
                logger.warning("Ollama returned empty extraction response")
                return [], []
            parsed = json.loads(content)

            entities = parsed.get("entities", [])
            relationships = parsed.get("relationships", [])
            return entities, relationships
        except json.JSONDecodeError as e:
            logger.error(f"Ollama Extraction JSON Error: {e}. Content: {content[:100]}")
            return [], []
        except Exception as e:
            logger.error(f"Ollama Extraction error: {e}")
            return [], []

    def embed(self, text: str) -> list[float]:
        # Compatibility: recent Ollama versions use /api/embed while older ones use /api/embeddings
        for endpoint in ["embed", "embeddings"]:
            data = {
                "model": self.model,
                "input": text if endpoint == "embed" else None,
                "prompt": text if endpoint == "embeddings" else None
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            try:
                # Use silent=True here to avoid logging 404 errors during the probing phase
                res = self._call_ollama(endpoint, data, silent=True)
                # handle different field names: 'embedding' (embeddings) or 'embeddings' (plural for embed)
                vec = res.get("embedding") or res.get("embeddings")
                if vec:
                    # In /api/embed (new API), it returns a list of vectors if multiple inputs are provided
                    # since we only pass one string as 'input', we might get [ [vector] ] or [vector]
                    if isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], list):
                        return vec[0]
                    return vec
            except Exception:
                continue # Try next endpoint if this one fails
        
        logger.error(f"Ollama Embedding failed: tried both 'embed' and 'embeddings' endpoints for model {self.model}. Check if the model supports embeddings and if the server is running.")
        return []


    def compare_entities(self, entity_a: str, entity_b: str) -> bool:
        prompt = f"Are the concepts '{entity_a}' and '{entity_b}' referring to the same thing in a knowledge graph? Answer only YES or NO."
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            res = self._call_ollama("generate", data)
            return "YES" in res.get("response", "").upper()
        except:
            return False

    def get_info(self) -> dict:
        return {
            "mode": "ollama",
            "model": self.model,
            "base_url": self.base_url
        }

def get_llm_provider(config_block: dict, root_config: dict = None) -> LLMProvider:
    """
    Factory to get an LLM provider based on a specific configuration block.
    config_block should be like settings['llm']['butler'] or settings['llm']['embeddings'].
    """
    mode = config_block.get("mode", "mock")
    if mode == "mock":
        return MockLLM()
    
    model_name = config_block.get("model_name")
    base_url = config_block.get("base_url")
    # API key resolution
    api_key_raw = config_block.get("api_key")
    api_key = None
    
    if api_key_raw:
        # If the string looks like a literal key (long or has key-specific prefix), use it directly.
        # OpenAI keys start with sk-, Gemini keys with AIza...
        if api_key_raw.startswith("sk-") or api_key_raw.startswith("AIza") or len(api_key_raw) > 30:
            api_key = api_key_raw
        else:
            # Otherwise treat it as an environment variable name
            api_key = os.getenv(api_key_raw)
            
    # Fallback finale
    if not api_key:
        api_key = config_block.get("api_key_value") or os.getenv("OPENAI_API_KEY")

    if not api_key and mode in ["openai", "remote"]:
        logger.error(f"LLM API Key missing for mode {mode}. Check settings.yaml or environment variables.")

    if mode == "openai":
        return OpenAILLM(
            api_key=api_key,
            model=model_name or "gpt-4o-mini",
            base_url=base_url,
            config=root_config or {"llm": config_block}
        )
    elif mode == "ollama":
        return OllamaLLM(
            base_url=base_url or "http://localhost:11434",
            model=model_name,
            config=root_config or {"llm": config_block}
        )
    elif mode == "remote":
        # Remote mode is basically OpenAI-compatible with a required base_url
        if not base_url:
            raise ValueError("Remote mode requires a base_url")
        return OpenAILLM(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            config=root_config or {"llm": config_block}
        )
    else:
        raise ValueError(f"Unknown LLM mode: {mode}")
