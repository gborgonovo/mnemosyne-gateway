"""
title: Mnemosyne Gateway Connector
author: GiodaLab
author_url: https://github.com/giodalab/mnemosyne
funding_url: https://github.com/giodalab/mnemosyne
version: 0.1.0
license: MIT
"""

import requests
import json
import re
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        mnemosyne_url: str = Field(
            default="http://host.docker.internal:4001",
            description="The URL of the Mnemosyne Gateway API."
        )
        enable_search: bool = Field(
            default=True,
            description="Enable context injection from Mnemosyne into the chat."
        )
        enable_learning: bool = Field(
            default=True,
            description="Enable learning when #memo is detected in the response."
        )
        memo_tag: str = Field(
            default="#memo",
            description="The tag used to trigger memory saving."
        )

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        print(f"DEBUG: Mnemosyne Inlet triggered. URL: {self.valves.mnemosyne_url}")
        if not self.valves.enable_search:
            print("DEBUG: Search is disabled in valves.")
            return body

        messages = body.get("messages", [])
        if not messages:
            print("DEBUG: No messages found in body.")
            return body

        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        if not last_user_message:
            print("DEBUG: No user message detected.")
            return body

        try:
            # 0. Debug message for visual confirmation
            messages.insert(-1, {"role": "system", "content": "🔍 Mnemosyne is searching..."})
            
            # 1. Fetch Briefing/Context
            print(f"DEBUG: Calling {self.valves.mnemosyne_url}/briefing")
            response = requests.get(f"{self.valves.mnemosyne_url}/briefing", timeout=5)
            print(f"DEBUG: Briefing response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                context_parts = []
                
                if data.get("hot_topics"):
                    context_parts.append(f"Hot Topics: {', '.join(data['hot_topics'])}")
                
                if data.get("butler_log"):
                    context_parts.append(f"The Butler's Insight: {data['butler_log']}")

                if context_parts:
                    context_msg = {
                        "role": "system",
                        "content": f"[MNEMOSYNE CONTEXT]\n" + "\n".join(context_parts)
                    }
                    messages.insert(-1, context_msg)
            
            # 2. Targeted Search
            keywords = last_user_message.split()
            found_concepts = []

            for word in keywords:
                if len(word) < 4: continue
                try:
                    search_resp = requests.get(f"{self.valves.mnemosyne_url}/search", params={"q": word}, timeout=2)
                    if search_resp.status_code == 200:
                        concept_data = search_resp.json()
                        details = f"- {concept_data['name']}: {json.dumps(concept_data['properties'])}"
                        if concept_data.get("related"):
                            details += f" (Related: {', '.join(concept_data['related'][:3])})"
                        found_concepts.append(details)
                    if len(found_concepts) >= 3: break
                except:
                    continue

            if found_concepts:
                print(f"DEBUG: Found {len(found_concepts)} concepts.")
                search_msg = {
                    "role": "system",
                    "content": f"[SPECIFIC MEMORIES FOUND]\n" + "\n".join(found_concepts)
                }
                messages.insert(-1, search_msg)
            
        except Exception as e:
            print(f"Mnemosyne Inlet Error: {e}")
            messages.insert(-1, {"role": "system", "content": f"⚠️ Mnemosyne Connection Error: {e}"})

        body["messages"] = messages
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.enable_learning:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last_assistant_message = messages[-1].get("content", "")
        # Find the last user message
        last_user_msg_idx = next((i for i in range(len(messages)-2, -1, -1) if messages[i]["role"] == "user"), None)
        last_user_input = messages[last_user_msg_idx]["content"] if last_user_msg_idx is not None else ""

        # Check if the tag is in either message
        user_tagged = self.valves.memo_tag in last_user_input
        assistant_tagged = self.valves.memo_tag in last_assistant_message

        if user_tagged or assistant_tagged:
            # 1. Prepare content to save
            # We strip the tags from the saved content to keep the graph clean
            clean_user = last_user_input.replace(self.valves.memo_tag, "").strip()
            clean_assistant = last_assistant_message.replace(self.valves.memo_tag, "").strip()
            content_to_save = f"User: {clean_user}\nAssistant: {clean_assistant}"
            
            try:
                # 2. Send to Mnemosyne
                requests.post(
                    f"{self.valves.mnemosyne_url}/add",
                    json={"content": content_to_save},
                    timeout=5
                )
                
                # 3. Clean the response for the user (remove tag from UI)
                if assistant_tagged:
                    body["messages"][-1]["content"] = clean_assistant
                
            except Exception as e:
                print(f"Mnemosyne Outlet Error: {e}")

        return body
