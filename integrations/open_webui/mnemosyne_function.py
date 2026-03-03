"""
title: Mnemosyne Gateway Connector
author: GiodaLab
author_url: https://github.com/giodalab/mnemosyne
funding_url: https://github.com/giodalab/mnemosyne
version: 0.2.0
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
        project_context: str = Field(
            default="",
            description="Specific project context to associate with these memories (e.g. 'Ganaghello'). Leave empty for general memory."
        )
        enable_search: bool = Field(
            default=True,
            description="Enable context injection from Mnemosyne into the chat."
        )
        search_context_limit: int = Field(
            default=2000,
            description="Maximum characters of context to inject to avoid overloading local models."
        )
        enable_continuous_learning: bool = Field(
            default=True,
            description="Enable continuous background learning of all conversation (unless incognito is active)."
        )
        incognito_command: str = Field(
            default="/incognito",
            description="Command to type in chat to disable memory saving and retrieval for the current session."
        )

    def __init__(self):
        self.valves = self.Valves()

    def _is_incognito(self, messages: list) -> bool:
        """Checks if the user has activated incognito mode in the current chat history."""
        for msg in messages:
            if msg.get("role") == "user" and self.valves.incognito_command in msg.get("content", ""):
                return True
        return False

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        print(f"DEBUG: Mnemosyne Inlet triggered. URL: {self.valves.mnemosyne_url}")
        if not self.valves.enable_search:
            print("DEBUG: Search is disabled in valves.")
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        if self._is_incognito(messages):
            print("DEBUG: Incognito mode active. Skipping Mnemosyne search.")
            return body

        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        if not last_user_message:
            return body

        try:
            context_parts = []
            
            # 1. Fetch Briefing/Context
            print(f"DEBUG: Calling {self.valves.mnemosyne_url}/briefing")
            response = requests.get(f"{self.valves.mnemosyne_url}/briefing", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("hot_topics"):
                    context_parts.append(f"Hot Topics: {', '.join(data['hot_topics'])}")
                if data.get("butler_log"):
                    context_parts.append(f"The Butler's Insight: {data['butler_log']}")

            # 2. Targeted Search
            search_query = last_user_message
            if self.valves.project_context:
                search_query = f"{self.valves.project_context} {search_query}"
                
            keywords = search_query.split()
            found_concepts = []

            # Reverse to give priority to the end of the sentence
            for word in reversed(keywords):
                if len(word) < 4: continue
                try:
                    search_resp = requests.get(f"{self.valves.mnemosyne_url}/search", params={"q": word}, timeout=2)
                    if search_resp.status_code == 200:
                        concept_data = search_resp.json()
                        details = f"- {concept_data['name']}: {concept_data.get('properties', {}).get('summary', '')}"
                        if concept_data.get("related"):
                            details += f" (Related: {', '.join(concept_data['related'][:3])})"
                        if details not in found_concepts:
                            found_concepts.append(details)
                    if len(found_concepts) >= 2: break
                except:
                    continue

            if found_concepts:
                context_parts.append(f"Specific Memories:\n" + "\n".join(found_concepts))
                
            if context_parts:
                full_context = "\n".join(context_parts)
                # Apply context length limit
                if len(full_context) > self.valves.search_context_limit:
                    full_context = full_context[:self.valves.search_context_limit] + "... (truncated)"
                    
                project_header = f"Project Context: {self.valves.project_context}\n" if self.valves.project_context else ""
                
                context_msg = {
                    "role": "system",
                    "content": f"[MNEMOSYNE CONTEXT]\n{project_header}{full_context}"
                }
                messages.insert(-1, context_msg)
            
        except Exception as e:
            print(f"Mnemosyne Inlet Error: {e}")

        body["messages"] = messages
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.enable_continuous_learning:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        if self._is_incognito(messages):
            print("DEBUG: Incognito mode active. Skipping Mnemosyne ingestion.")
            return body

        last_assistant_message = messages[-1].get("content", "").strip()
        last_user_msg_idx = next((i for i in range(len(messages)-2, -1, -1) if messages[i]["role"] == "user"), None)
        last_user_input = messages[last_user_msg_idx]["content"].strip() if last_user_msg_idx is not None else ""

        if last_user_input and last_assistant_message:
            content_to_save = f"User: {last_user_input}\nAssistant: {last_assistant_message}"
            
            try:
                payload = {
                    "content": content_to_save
                }
                # Inject project context directly into the text for the PerceptionModule
                if self.valves.project_context:
                    payload["content"] = f"[Project context: {self.valves.project_context}]\n" + content_to_save
                
                requests.post(
                    f"{self.valves.mnemosyne_url}/add",
                    json=payload,
                    timeout=5
                )
                print("DEBUG: Memory segment successfully sent to Mnemosyne.")
            except Exception as e:
                print(f"Mnemosyne Outlet Error: {e}")

        return body
