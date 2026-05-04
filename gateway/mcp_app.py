from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
import uuid
import re
import os
import yaml
from datetime import datetime

def create_mcp_server(kuzu_mgr, vector_store, am, gd, config, knowledge_dir):
    # Security Configuration for Remote Access
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["memory.borgonovo.org:*", "memory.borgonovo.org", "localhost:*", "localhost", "127.0.0.1:*", "127.0.0.1"],
        allowed_origins=["https://claude.ai", "https://memory.borgonovo.org", "http://localhost:*", "http://127.0.0.1:*"]
    )
    
    mcp = FastMCP("Mnemosyne-Memory", transport_security=security)

    # Helper functions
    def find_file_recursive(name: str):
        """Locate a markdown file by name (case-insensitive) anywhere within the knowledge directory."""
        safe_name = re.sub(r'[^\w\s-]', '', name).strip().lower()
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                if f.lower() == f"{safe_name}.md":
                    return os.path.join(root, f)
        return None

    def read_markdown(name: str):
        path = find_file_recursive(name)
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def write_markdown(name: str, frontmatter: dict, body: str):
        # Try to find existing file to update it in place
        path = find_file_recursive(name)
        if not path:
            # New file, put it in the root
            safe_name = re.sub(r'[^\w\s-]', '', name).strip()
            path = os.path.join(knowledge_dir, f"{safe_name}.md")
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
            f.write("---\n\n")
            f.write(body)

    @mcp.tool()
    def trigger_gardening_cycle() -> str:
        """
        Manually trigger a gardening cycle to apply temporal decay to network heat.
        """
        gd.run_once()
        return "Gardening cycle completed successfully. Memory network heat decayed."

    @mcp.tool()
    def query_knowledge(query: str, limit: int = 3) -> str:
        """Semantic search of the Mnemosyne knowledge base."""
        results = vector_store.semantic_search(query, limit=limit * 2)
        if not results:
            return f"No concepts matching '{query}' found in memory."
            
        ranked_results = []
        for r in results:
            name = r['name']
            node_state = kuzu_mgr.get_node(name)
            heat = node_state['activation_level'] if node_state else 0.1
            combined_score = (1.0 / (r['distance'] + 0.001)) * (heat + 0.5)
            ranked_results.append((combined_score, name))
            
        ranked_results.sort(key=lambda x: x[0], reverse=True)

        output = ""
        for score, name in ranked_results[:limit]:
            content = read_markdown(name)
            if content:
                output += f"### FILE: {name}.md (Relevance Score: {score:.2f})\n```markdown\n{content}\n```\n\n"
                am.record_interaction(name, interaction_type="mcp_query")
        return output

    @mcp.tool()
    def add_observation(content: str, scope: str = "Public") -> str:
        """Record a new raw piece of unstructured information into memory."""
        obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
        frontmatter = {"type": "Observation", "scope": scope}
        try:
            write_markdown(obs_id, frontmatter, content)
            return f"Observation recorded as {obs_id}.md in scope '{scope}'."
        except Exception as e:
            return f"Error recording observation: {e}"

    @mcp.tool()
    def get_memory_briefing() -> str:
        """Get a briefing on currently active (hot) topics."""
        active_nodes = kuzu_mgr.get_active_nodes(threshold=0.5)
        if not active_nodes:
             return "The memory is currently resting. No active thoughts."
             
        active_nodes.sort(key=lambda x: x['activation_level'], reverse=True)
        hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("Obs_")][:10]

        briefing = "Current active internal thoughts (Hot Nodes):\n"
        for title in hot_topics:
            content = read_markdown(title)
            preview = content[:150].replace('\n', ' ') + "..." if content else "File not found"
            briefing += f"- {title} (Context: {preview})\n"

        dormant_cfg = config.get("attention", {}).get("dormant", {})
        dormant_nodes = kuzu_mgr.get_dormant_nodes(
            min_interactions=dormant_cfg.get("min_interactions", 5),
            days_node=dormant_cfg.get("days_node", 27),
            days_goal_task=dormant_cfg.get("days_goal_task", 30),
        )
        if dormant_nodes:
            briefing += "\nDormienti (erano attivi, ora inattivi):\n"
            for n in dormant_nodes[:5]:
                briefing += f"- {n['name']} ({n['node_type']}, inattivo da {n['days_inactive']}gg)\n"
        return briefing

    @mcp.tool()
    def get_system_status() -> str:
        """Checks the status of the hybrid architecture databases and file system."""
        all_md_files = []
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                if f.endswith('.md'):
                    all_md_files.append(os.path.join(root, f))

        status = {
            "timestamp": datetime.now().isoformat(),
            "architecture": "Hybrid File-First",
            "file_system": {
                "base_path": knowledge_dir,
                "total_markdown_files": len(all_md_files),
                "top_level_files": len([f for f in os.listdir(knowledge_dir) if f.endswith('.md')])
            },
            "kuzu_thermal_graph": {
                "active_nodes": len(kuzu_mgr.get_active_nodes(threshold=0.1))
            },
            "chromadb_semantic": {
                "total_documents": len(vector_store.list_nodes())
            }
        }
        return json.dumps(status, indent=2)

    @mcp.tool()
    def debug_filesystem() -> str:
        """Lists all files found by the recursive search to debug path issues."""
        files_found = []
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                files_found.append(os.path.relpath(os.path.join(root, f), knowledge_dir))
        return "\n".join(files_found)

    @mcp.tool()
    def inspect_file_raw(name: str) -> str:
        """Read the direct markdown file from the file system."""
        content = read_markdown(name)
        if not content:
            return json.dumps({"error": f"File '{name}.md' not found"}, indent=2)
        return content

    @mcp.tool()
    def forget_knowledge_node(name: str) -> str:
        """Completely erases a concept by deleting its Markdown file."""
        path = find_file_recursive(name)
        if path and os.path.exists(path):
             os.remove(path)
             return json.dumps({"status": "success", "message": f"File '{name}.md' deleted."}, indent=2)
        return json.dumps({"status": "error", "message": f"File '{name}.md' not found."}, indent=2)

    @mcp.tool()
    def update_knowledge_frontmatter(name: str, updates: str) -> str:
        """Updates the YAML frontmatter properties of an existing entity."""
        path = find_file_recursive(name)
        if not path or not os.path.exists(path):
            return json.dumps({"status": "error", "message": f"Entity '{name}' not found."})
        try:
            properties_dict = json.loads(updates)
        except json.JSONDecodeError:
             return json.dumps({"error": "The 'updates' argument must be valid JSON."})
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
            if yaml_match:
                frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
                body = yaml_match.group(2)
            else:
                frontmatter = {}
                body = content
            for k, v in properties_dict.items():
                 frontmatter[k] = v
            write_markdown(name, frontmatter, body)
            return json.dumps({"status": "success", "message": f"File '{name}.md' frontmatter updated."})
        except Exception as e:
             return json.dumps({"error": str(e)})

    @mcp.tool()
    def create_goal(name: str, description: str = "", deadline: str = "", scopes: str = "Private,Public") -> str:
        """Creates a new high-level strategic Goal as a Markdown file."""
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        frontmatter = {"type": "Goal", "status": "active", "scope": scope_list[0]}
        if deadline: frontmatter["deadline"] = deadline
        body = f"# {name}\n\n{description}"
        write_markdown(name, frontmatter, body)
        return json.dumps({"status": "success", "message": f"Goal '{name}' created."})

    @mcp.tool()
    def create_task(name: str, goal_name: str, description: str = "", due_date: str = "", scopes: str = "Private,Public") -> str:
        """Creates an actionable Task and links it to an existing Goal via wikilinks."""
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        frontmatter = {"type": "Task", "status": "todo", "scope": scope_list[0]}
        if due_date: frontmatter["due_date"] = due_date
        body = f"# {name}\n\n**Linked Goal:** [[{goal_name}]]\n\n{description}"
        write_markdown(name, frontmatter, body)
        return json.dumps({"status": "success", "message": f"Task '{name}' created and linked to '{goal_name}'."})

    @mcp.tool()
    def update_task_status(name: str, status: str) -> str:
        """Updates the status of a Task or Goal."""
        return update_knowledge_frontmatter(name, json.dumps({"status": status}))

    return mcp
