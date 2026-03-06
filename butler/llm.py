from abc import ABC, abstractmethod
import random
import logging
import requests
import json
import os

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
    def extract_entities(self, text: str, context_nodes: list[str] = None) -> tuple[list[dict], list[dict]]:
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

    def extract_entities(self, text: str, context_nodes: list[str] = None) -> tuple[list[dict], list[dict]]:
        logger.info(f"MOCK LLM EXTRACTION\nText: {text[:50]}...")
        # Simple heuristic for testing: treat capitalized words as entities
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
            return "Mi scusi signore, sto riscontrando qualche difficoltà nel processare la sua richiesta."

    def extract_entities(self, text: str, context_nodes: list[str] = None) -> tuple[list[dict], list[dict]]:
        context_nodes = context_nodes or []
        context_info = ""
        if context_nodes:
            context_info = f"\nCurrently active nodes in the graph: {', '.join(context_nodes)}. If any extracted entity is a synonym or closely relates to these, prioritize using the existing node name."

        prompt = f"""
        Extract key entities and topics from the following text.{context_info}
        Structure your response as a JSON object with two keys:
        1. "entities": a list of objects, each with 'name' (the label) and 'type' (Entity, Topic, Resource, Goal, or Task).
        2. "relationships": a list of objects, each representing an explicit link between two extracted entities. Each must have 'source', 'target', and 'type' (a screaming snake case verb EXCLUSIVELY from this list: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A).
        
        - Entity: Concrete items (People, Tools, Places, specific things the user mentions).
        - Topic: Abstract themes or ideas.
        - Resource: Digital artifacts (Files, Links).
        - Goal: Long-term objectives (e.g., 'Launch the B&B').
        - Task: Specific actions or commitments (e.g., 'Fix the sink', 'Call the bank'). Tasks should also extract 'status' (todo/done) and 'deadline' if mentioned.
        
        CRITICAL INSTRUCTIONS:
        1. If the user is ASKING about something (e.g., "Parlami della stalla", "Cosa sai del progetto X?"), extract the SUBJECT of their question as an Entity.
        2. Ignore generic adjectives (e.g., 'interessante', 'utile'), conversational fillers, or common verbs.
        3. Focus on nouns, proper names, and well-defined technical terms.
        4. Even simple requests like "Tell me about X" should extract X as an entity.
        5. Extract clear, direct relationships. If A is a project of B, the relationship is A -> PART_OF -> B. If two concepts are similar/congruent, map A -> RELATED_TO -> B.
        
        Text: {text}
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a specialized entity extractor. Return only JSON."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            logger.debug(f"LLM Response: {content}")
            data = json.loads(content)
            
            # Be flexible with response format
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

class OllamaLLM(LLMProvider):
    """Real implementation connecting to Ollama."""
    
    def __init__(self, base_url: str, model: str, config: dict = None):
        self.base_url = base_url
        self.model = model
        self.config = config or {}

    def _call_ollama(self, endpoint: str, data: dict, timeout: int = 30) -> dict:
        url = f"{self.base_url.rstrip('/')}/api/{endpoint}"
        try:
            response = requests.post(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ollama API error ({url}): {e}")
            raise
    
    # ... (generate, generate_response, extract_entities are the same as before but using self.model and self.base_url)

    def generate(self, prompt: str, context: dict = None, timeout: int = 30) -> str:
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        res = self._call_ollama("generate", data, timeout=timeout)
        return res.get("response", "")

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
            return "Mi scusi signore, sto riscontrando qualche difficoltà nel processare la sua richiesta locale."

    def extract_entities(self, text: str, context_nodes: list[str] = None) -> tuple[list[dict], list[dict]]:
        context_nodes = context_nodes or []
        context_info = ""
        if context_nodes:
            context_info = f"\nCurrently active nodes in the graph: {', '.join(context_nodes)}. If any extracted entity is a synonym or closely relates to these, prioritize using the existing node name."

        prompt = f"""
        Extract key entities and topics from the following text.{context_info}
        Structure your response as a JSON object with two keys:
        1. "entities": a list of objects, each with 'name' (the label) and 'type' (Entity, Topic, Resource, Goal, or Task).
        2. "relationships": a list of objects, each representing an explicit link between two extracted entities. Each must have 'source', 'target', and 'type' (a screaming snake case verb EXCLUSIVELY from this list: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A).
        
        - Entity: Concrete items (People, Tools, Places, specific things the user mentions).
        - Topic: Abstract themes or ideas.
        - Resource: Digital artifacts (Files, Links).
        - Goal: Long-term objectives (e.g., 'Launch the B&B').
        - Task: Specific actions or commitments (e.g., 'Fix the sink', 'Call the bank'). Tasks should also extract 'status' (todo/done) and 'deadline' if mentioned.
        
        CRITICAL INSTRUCTIONS:
        1. If the user is ASKING about something (e.g., "Parlami della stalla", "Cosa sai del progetto X?"), extract the SUBJECT of their question as an Entity.
        2. Ignore conversational fillers or common verbs.
        3. Return ONLY the JSON object. No preamble or postscript.
        4. Extract clear, direct relationships. If A is a project of B, the relationship is A -> PART_OF -> B. If two concepts are similar/congruent, map A -> RELATED_TO -> B.
        
        Text: {text}
        """
        data = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }
        try:
            res = self._call_ollama("generate", data)
            content = res.get("response", "{}")
            logger.debug(f"Ollama Extraction Response: {content}")
            if not content or content.strip() == "":
                logger.warning("Ollama returned empty extraction response")
                return [], []
            data = json.loads(content)
            
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            return entities, relationships
        except json.JSONDecodeError as e:
            logger.error(f"Ollama Extraction JSON Error: {e}. Content: {content[:100]}")
            return [], []
        except Exception as e:
            logger.error(f"Ollama Extraction error: {e}")
            return [], []

    def embed(self, text: str) -> list[float]:
        data = {
            "model": self.model,
            "prompt": text
        }
        try:
            res = self._call_ollama("embeddings", data)
            return res.get("embedding", [])
        except Exception as e:
            logger.error(f"Ollama Embedding error: {e}")
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
    # API key from config or env
    api_key_name = config_block.get("api_key") # e.g. "OPENAI_API_KEY"
    api_key = os.getenv(api_key_name) if api_key_name else None
    
    # Fallback to direct key or standard env if not specified
    if not api_key:
        api_key = config_block.get("api_key_value") or os.getenv("OPENAI_API_KEY")

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
