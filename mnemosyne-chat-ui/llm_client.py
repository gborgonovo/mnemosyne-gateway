import os
from openai import OpenAI
from typing import List, Dict, Any, Generator

from config_reader import get_llm_config

def get_client():
    config = get_llm_config()
    mode = config.get("mode", "mock")
    
    if mode == "mock":
        return None # We handle mock locally
        
    api_key = config.get("api_key", "sk-dummy")
    
    # If using local ollama or openai-compatible remote
    if mode in ["ollama", "remote"]:
        base_url = config.get("base_url")
        if mode == "ollama" and not base_url:
            base_url = "http://localhost:11434/v1"
            
        return OpenAI(
            base_url=base_url,
            api_key=api_key or "sk-dummy"
        )
        
    # Standard OpenAI
    if mode == "openai":
        # Resolve real apikey from environment if it was just a variable name
        env_key = os.environ.get(api_key, api_key)
        return OpenAI(api_key=env_key)
        
    return None

def generate_chat_stream(messages: List[Dict[str, str]]) -> Generator[str, None, None]:
    config = get_llm_config()
    mode = config.get("mode", "mock")
    model_name = config.get("model_name", "gpt-4o-mini")
    
    if mode == "mock":
        # Mock streaming response
        mock_response = "Questa è una risposta simulata (Mock Mode). Configura The Butler in `settings.yaml` per risposte reali."
        for word in mock_response.split():
            yield word + " "
        return

    client = get_client()
    if not client:
        yield "Errore: Client LLM non configurato."
        return
        
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"Errore durante la generazione: {str(e)}"

def generate_chat_title(messages: List[Dict[str, str]]) -> str:
    """Produce un titolo breve (max 5-6 parole) per la conversazione."""
    config = get_llm_config()
    mode = config.get("mode", "mock")
    model_name = config.get("model_name", "gpt-4o-mini")
    
    if mode == "mock":
        return "Conversazione " + messages[-1]["content"][:15] + "..."
        
    client = get_client()
    if not client:
        return "Nuova Conversazione"
        
    prompt = [
        {"role": "system", "content": "Genera un titolo molto breve (massimo 5 parole) per questa conversazione. Rispondi SOLO con il titolo, senza virgolette e senza testo aggiuntivo."},
    ]
    # Includi solo gli ultimi messaggi per il contesto (massimo 2)
    prompt.extend([m for m in messages if m["role"] in ["user", "assistant"]][-2:])
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=prompt,
            max_tokens=20,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Nuova Conversazione"
