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
            default="http://host.docker.internal:8000",
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
        if not self.valves.enable_search:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), None)
        if not last_user_message:
            return body

        try:
            # 1. Fetch Briefing/Context
            response = requests.get(f"{self.valves.mnemosyne_url}/briefing", timeout=5)
            if response.status_code == 200:
                data = response.json()
                context_parts = []
                
                if data.get("hot_topics"):
                    context_parts.append(f"Hot Topics: {', '.join(data['hot_topics'])}")
                
                if data.get("alfred_log"):
                    context_parts.append(f"Alfred's Insight: {data['alfred_log']}")

                if context_parts:
                    context_msg = {
                        "role": "system",
                        "content": f"[MNEMOSYNE CONTEXT]\n" + "\n".join(context_parts)
                    }
                    messages.insert(-1, context_msg)
            
            # 2. Add selective search for the last message
            # (Optional: limit searching to avoid too many injections)
            
        except Exception as e:
            print(f"Mnemosyne Inlet Error: {e}")

        body["messages"] = messages
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.enable_learning:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last_assistant_message = messages[-1].get("content", "")
        if self.valves.memo_tag in last_assistant_message:
            # 1. Identify what to save (User input + Assistant response)
            # Find the last user message for full context
            last_user_input = next((m["content"] for m in reversed(messages[:-1]) if m["role"] == "user"), "")
            
            content_to_save = f"User: {last_user_input}\nAssistant: {last_assistant_message}"
            
            try:
                # 2. Send to Mnemosyne
                requests.post(
                    f"{self.valves.mnemosyne_url}/add",
                    json={"content": content_to_save},
                    timeout=5
                )
                
                # 3. Clean the response for the user
                cleaned_content = last_assistant_message.replace(self.valves.memo_tag, "").strip()
                body["messages"][-1]["content"] = cleaned_content
                
            except Exception as e:
                print(f"Mnemosyne Outlet Error: {e}")

        return body
