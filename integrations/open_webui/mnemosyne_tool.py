"""
title: Mnemosyne Memory Search
author: GiodaLab
author_url: https://github.com/giodalab/mnemosyne
version: 0.1.0
description: A tool that allows the LLM to search for past memories, concepts, and project contexts stored in Mnemosyne.
"""

import requests
import json
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        mnemosyne_url: str = Field(
            default="http://host.docker.internal:4001",
            description="The URL of the Mnemosyne Gateway API."
        )

    def __init__(self):
        self.valves = self.Valves()

    def search_memory(self, query: str, project_context: str = "") -> str:
        """
        Search for information, past memories, or concepts inside the Mnemosyne cognitive layer.
        Use this tool when the user asks about past events, project details, or concepts you don't know about.

        :param query: The search query, keywords, or the concept to look for.
        :param project_context: (Optional) The specific project or category to focus the search on (e.g., 'Ganaghello').
        :return: A string containing the semantic matches found in Mnemosyne.
        """
        try:
            # If a project context is provided, we can prepend it to the query to guide the semantic search
            search_query = f"{project_context} {query}".strip()
            print(f"DEBUG Tool: Searching Mnemosyne for '{search_query}'")
            
            response = requests.get(
                f"{self.valves.mnemosyne_url}/search", 
                params={"q": search_query}, 
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                result_str = f"Concept Found: {data.get('name', 'Unknown')}\n"
                
                # We format the properties to be easily readable by the LLM
                props = data.get("properties", {})
                
                if "summary" in props:
                    result_str += f"Summary: {props['summary']}\n"
                elif "description" in props:
                    result_str += f"Description: {props['description']}\n"
                    
                # Format other properties
                other_props = {k: v for k, v in props.items() if k not in ['summary', 'description', 'type', 'slug', 'name']}
                if other_props:
                    result_str += f"Details: {json.dumps(other_props)}\n"
                    
                related = data.get("related", [])
                if related:
                    result_str += f"Related concepts: {', '.join(related[:5])}\n"
                    
                return result_str
            elif response.status_code == 404:
                return f"No memories or concepts found matching: '{query}' in project '{project_context}'."
            else:
                return f"Failed to search memory. Status code: {response.status_code}"
                
        except Exception as e:
            return f"Error while connecting to Mnemosyne: {str(e)}"
