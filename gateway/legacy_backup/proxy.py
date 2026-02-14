from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
import httpx
import json
from .state import state

router = APIRouter(tags=["proxy"])

# --- Pydantic Models for OpenAI API Compatibility ---

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

# --- Proxy Logic ---

@router.get("/v1")
async def v1_root():
    return {"status": "ok", "message": "Mnemosyne V1 API Proxy Active"}


@router.get("/v1/models")
@router.get("/models")
async def list_models():
    """
    Lists the available models. Open WebUI needs this for discovery.
    """
    print("🔍 DISCOVERY: Open WebUI requested model list")
    config = state.config.get('llm', {})
    display_name = config.get('display_name', config.get('model_name', 'mnemosyne'))
    
    # Return a more complete OpenAI-like response
    return {
        "object": "list",
        "data": [
            {
                "id": display_name,
                "object": "model",
                "created": 1700000000,
                "owned_by": "mnemosyne",
                "permission": [],
                "root": display_name,
                "parent": None
            }
        ]
    }




@router.post("/v1/chat/completions")
@router.post("/chat/completions")
async def proxy_chat_completions(request: ChatCompletionRequest, raw_request: Request):
    print(f"📥 CHAT: {request.model}")


    """
    Acts as a middleware for OpenAI-compatible chat completions.
    Intercepts the last user message, retrieves context from Mnemosyne,
    injects it into the prompt, and forwards to the real LLM.
    """
    
    # 1. Identify the last user message
    last_user_msg_index = -1
    for i, msg in enumerate(reversed(request.messages)):
        if msg.role == "user":
            last_user_msg_index = len(request.messages) - 1 - i
            break
            
    if last_user_msg_index == -1:
        # No user message found, just forward
        return await forward_request(request)
    
    user_content = request.messages[last_user_msg_index].content
    
    # 2. Perception & Context Retrieval (The "Mnemosyne" Step)
    context_injection = ""
    if state.pm and state.gm:
        # Extract entities
        entities = state.pm.process_input(user_content)
        
        if entities:
            # Retrieve details from Graph
            context_fragments = []
            for entity in entities:
                # 1. SKIP technical nodes
                if entity.startswith("Obs_"): continue
                node = state.gm.get_node(entity)
                if not node or "Observation" in node.get('labels', []): continue

                # 2. Prepare Header
                clean_labels = [l for l in node.get('labels', []) if l not in ["Node", "Entity", "Topic"]]
                label_str = f" ({', '.join(clean_labels)})" if clean_labels else ""
                frag = f"--- [CONCEPT: {entity.upper()}{label_str}] ---\n"
                
                # 3. Fetch Properties (The 'Facts')
                props = {k: v for k, v in dict(node).items() if k not in ['name', 'last_seen', 'activation_level', 'labels']}
                if props:
                    frag += "Properties:\n"
                    for k, v in props.items():
                        frag += f"  - {k}: {v}\n"
                
                # 4. Fetch Neighbors (Contextual cloud)
                neighbors = state.gm.get_neighbors(entity)
                semantic_neighbors = [
                    n['node']['name'] for n in neighbors 
                    if "Observation" not in n['node'].get('labels', [])
                    and not n['node']['name'].startswith("Obs_")
                ]
                if semantic_neighbors:
                    frag += f"Related Context: {', '.join(semantic_neighbors[:8])}\n"
                
                # 5. FETCH EPISTEMIC MEMORY (Observations)
                with state.gm.driver.session() as session:
                    obs_query = """
                    MATCH (n)-[:MENTIONED_IN]->(o:Observation)
                    WHERE toLower(n.name) = toLower($name)
                    RETURN o.content as content
                    ORDER BY o.timestamp DESC LIMIT 5
                    """
                    results = session.run(obs_query, name=entity)
                    memories = [record['content'] for record in results]
                    
                    # Anti-Circular Filter
                    valid_memory = [m for m in memories if m.strip().lower() != user_content.strip().lower()]

                    # NEIGHBOR LURK: If direct info is missing, pull from relatives
                    if (not valid_memory or len(valid_memory) < 2) and semantic_neighbors:
                        for rel in semantic_neighbors[:3]:
                            rel_results = session.run(obs_query, name=rel)
                            for r in rel_results:
                                if r['content'].strip().lower() != user_content.strip().lower():
                                    valid_memory.append(f"(Source {rel}): {r['content']}")
                            
                    if valid_memory:
                        frag += f"Personal Memories & Past Statements:\n"
                        unique_mem = list(dict.fromkeys(valid_memory)) # Dedup
                        for m in unique_mem[:10]:
                            # Final Sanitization: Clean multiline and hide LEAKED IDs
                            clean_m = " ".join(m.split())
                            if "Obs_" in clean_m: continue 
                            frag += f"  * \"{clean_m[:800]}\"\n"

                context_fragments.append(frag)

            # 6. GLOBAL CONTEXT (Active topics awareness)
            if state.gm:
                active = state.gm.get_active_nodes(threshold=0.8)
                hot = [n['name'] for n in active if n['name'] not in entities and not n['name'].startswith("Obs_")]
                if hot:
                    context_fragments.append(f"--- [CURRENTLY ACTIVE TOPICS] ---\n{', '.join(hot[:15])}\n")

            if context_fragments:
                # FINAL FILTER: Force clean all IDs
                raw_txt = "\n".join(context_fragments)
                clean_lines = [l for l in raw_txt.split("\n") if "Obs_" not in l]
                
                context_injection = "=== [MNEMOSYNE MEMORY RETRIEVAL] ===\n"
                context_injection += "CRITICAL: The following are verified facts and personal user statements. Trust this over your training data.\n\n"
                context_injection += "\n".join(clean_lines)
                context_injection += "\n=== [END OF MNEMOSYNE CONTEXT] ===\n"




    # 3. Injection Strategy
    if context_injection:
        # We append the context to the last user message to ensure it's "seen" by the model as immediate context
        # Alternatively, we could add a System message, but prepending to User is often more robust for smaller models (like 7B).
        original_content = request.messages[last_user_msg_index].content
        new_content = f"{context_injection}\n\nUser Query: {original_content}"
        request.messages[last_user_msg_index].content = new_content
        
        print(f"💉 Injected Context for entities: {entities}")

    # 4. Forward to upstream LLM
    return await forward_request(request)

async def forward_request(request: ChatCompletionRequest):
    """
    Forwards the (possibly modified) request to the upstream LLM.
    """
    # Get configuration
    llm_config = state.config.get('llm', {})
    base_url = llm_config.get('ollama_url', llm_config.get('base_url', 'http://localhost:11434'))
    api_key = llm_config.get('api_key', 'ollama') # Ollama doesn't care, OpenAI does
    
    upstream_url = f"{base_url}/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    timeout = httpx.Timeout(60.0, read=120.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # Streaming is complex to proxy perfectly in a simple MVP without proper async generator chaining.
            # For MVP, we will force stream=False or handle non-streaming only.
            # If user requested stream=True, we might warn or just return full response.
            # Let's support non-streaming first.
            if request.stream:
                # TODO: Implement streaming proxy
                pass
            
            payload = request.model_dump(exclude_none=True)
            # OVERRIDE: Ensure we use the real model name for the upstream LLM
            # (Clients might send the display name 'Alfred')
            payload['model'] = llm_config.get('model_name', 'qwen2.5:7b')
            # FORCE non-streaming for MVP (streaming requires SSE handling)
            payload['stream'] = False
            
            print(f"📡 Forwarding to Upstream: {upstream_url} (Model: {payload['model']}, Stream: {payload['stream']})")

            response = await client.post(upstream_url, json=payload, headers=headers)

            print(f"📥 Upstream Response Status: {response.status_code}")
            
            if response.status_code != 200:
                 print(f"❌ Upstream Error Body: {response.text}")
                 raise HTTPException(status_code=response.status_code, detail=f"Upstream Error: {response.text}")
            
            try:
                resp_json = response.json()
                if not resp_json:
                    print("⚠️ Upstream returned empty JSON")
                return resp_json
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}")
                print(f"Raw Response Text (first 500 chars): {response.text[:500]}")
                raise HTTPException(status_code=500, detail=f"Invalid JSON from upstream: {str(e)}")


            
        except httpx.RequestError as exc:
            print(f"❌ HTTPX Request Error: {exc}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=502, detail=f"An error occurred while requesting {exc.request.url!r}. Error: {str(exc)}")
