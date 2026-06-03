from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
import uuid
import re
import os
import yaml
from datetime import datetime

from core.utils import strip_leading_frontmatter


def create_mcp_server(kuzu_mgr, vector_store, am, gd, config, knowledge_dir):
    # Security Configuration for Remote Access
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["memory.borgonovo.org:*", "memory.borgonovo.org", "localhost:*", "localhost", "127.0.0.1:*", "127.0.0.1"],
        allowed_origins=["https://claude.ai", "https://memory.borgonovo.org", "http://localhost:*", "http://127.0.0.1:*"]
    )
    
    mcp = FastMCP("Mnemosyne-Memory", transport_security=security, streamable_http_path="/", stateless_http=True)

    # Helper functions
    def find_file_recursive(name: str):
        """Locate a markdown file within the knowledge directory.

        Accepts either a bare node name (case-insensitive basename match,
        searched recursively) or a relative path including subfolders,
        e.g. 'Sistema/Alfred/System Prompt Alfred 3.0'. A trailing '.md'
        extension is optional in both forms.
        """
        if not name:
            return None

        cleaned = name.strip().replace("\\", "/")
        if cleaned.lower().endswith(".md"):
            cleaned = cleaned[:-3]

        base = os.path.abspath(knowledge_dir)

        # 1) Relative path including subfolders → resolve directly under knowledge_dir.
        if "/" in cleaned:
            candidate = os.path.abspath(os.path.join(base, cleaned + ".md"))
            # Guard against path traversal outside the knowledge directory.
            if (candidate == base or candidate.startswith(base + os.sep)) and os.path.isfile(candidate):
                return candidate

        # 2) Fall back to a recursive case-insensitive basename match.
        target = os.path.basename(cleaned).lower()
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                if f.lower() == f"{target}.md":
                    return os.path.join(root, f)
        return None

    def read_markdown(name: str):
        path = find_file_recursive(name)
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def write_markdown(name: str, frontmatter: dict, body: str, folder: str = ""):
        # Guard: never let a frontmatter block end up embedded in the body
        # (e.g. when a caller passes raw file content as the new body).
        body = strip_leading_frontmatter(body)
        # Try to find existing file to update it in place
        path = find_file_recursive(name)
        is_new = path is None
        if not path:
            if folder:
                target_dir = os.path.join(knowledge_dir, folder)
                if not os.path.isdir(target_dir):
                    raise ValueError(f"Folder '{folder}' does not exist. Use create_project first.")
            else:
                target_dir = knowledge_dir
            safe_name = re.sub(r'[^\w\s-]', '', name).strip()
            path = os.path.join(target_dir, f"{safe_name}.md")

        if is_new and 'created_at' not in frontmatter:
            frontmatter['created_at'] = datetime.now().strftime('%Y-%m-%d')

        with open(path, 'w', encoding='utf-8') as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
            f.write("---\n\n")
            f.write(body)

    def _parse_relations(relations_str: str) -> list:
        """Parse 'Target:TYPE,Other:PART_OF' into [{target, type}, ...] for frontmatter."""
        result = []
        for item in relations_str.split(","):
            item = item.strip()
            if not item:
                continue
            if ":" in item:
                target, rel_type = item.rsplit(":", 1)
                result.append({"target": target.strip(), "type": rel_type.strip().upper()})
            else:
                result.append({"target": item, "type": "RELATED_TO"})
        return result

    def _normalize_folder_name(name: str) -> str:
        return re.sub(r'[\s_\-]+', '', name).lower()

    def _folder_tree(base_dir: str, prefix: str = "") -> str:
        try:
            entries = sorted(os.listdir(base_dir))
        except PermissionError:
            return ""
        dirs = [e for e in entries if os.path.isdir(os.path.join(base_dir, e))
                and not e.startswith('_') and not e.startswith('.')]
        lines = []
        for d in dirs:
            dir_path = os.path.join(base_dir, d)
            defaults_path = os.path.join(dir_path, '_defaults.yaml')
            meta = ""
            if os.path.exists(defaults_path):
                try:
                    with open(defaults_path) as f:
                        defaults = yaml.safe_load(f) or {}
                    parts = []
                    if 'scope' in defaults:
                        parts.append(f"scope={defaults['scope']}")
                    if 'description' in defaults:
                        parts.append(f"'{defaults['description']}'")
                    if parts:
                        meta = f" [{', '.join(parts)}]"
                except Exception:
                    pass
            lines.append(f"{prefix}{d}/{meta}")
            subtree = _folder_tree(dir_path, prefix + "  ")
            if subtree:
                lines.append(subtree)
        return "\n".join(lines)

    @mcp.tool()
    def list_projects() -> str:
        """
        List all project folders in the knowledge base as an indented tree.
        Call this before create_project to check if a suitable folder already exists.
        """
        tree = _folder_tree(knowledge_dir)
        if not tree:
            return "No project folders found in the knowledge base."
        return f"Knowledge folder structure:\n\n{tree}"

    @mcp.tool()
    def create_project(name: str, description: str = "", scope: str = "Private", parent: str = "") -> str:
        """
        Create a new project folder in the knowledge base.
        IMPORTANT: Call list_projects first to check if a suitable folder already exists.

        name: folder name (will be sanitized; spaces become underscores)
        description: optional description, saved as index file and in _defaults.yaml
        scope: default scope for files in this folder ('Private' or 'Public')
        parent: relative path of an existing folder (e.g. 'Ganaghello/Operativo');
                leave empty to create at root level
        """
        if parent:
            base_path = os.path.join(knowledge_dir, parent)
            if not os.path.isdir(base_path):
                return json.dumps({"status": "error", "message": f"Parent folder '{parent}' does not exist. Use list_projects to see available folders."})
        else:
            base_path = knowledge_dir

        safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

        existing_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and not d.startswith('_')]
        for existing in existing_dirs:
            if existing.lower() == safe_name.lower():
                tree = _folder_tree(knowledge_dir)
                return json.dumps({"status": "error", "message": f"Folder '{existing}' already exists at this level. Use it or choose a different name.\n\nCurrent structure:\n{tree}"})

        warnings = [e for e in existing_dirs if _normalize_folder_name(e) == _normalize_folder_name(safe_name)]

        folder_path = os.path.join(base_path, safe_name)
        os.makedirs(folder_path, exist_ok=True)

        defaults = {"project": name, "scope": scope}
        if description:
            defaults["description"] = description
        with open(os.path.join(folder_path, '_defaults.yaml'), 'w') as f:
            yaml.dump(defaults, f, allow_unicode=True, default_flow_style=False)

        if description:
            index_frontmatter = {"type": "Node", "scope": scope, "created_at": datetime.now().strftime('%Y-%m-%d')}
            index_body = f"# {name}\n\n{description}"
            with open(os.path.join(folder_path, f"{safe_name}.md"), 'w') as f:
                f.write("---\n")
                yaml.dump(index_frontmatter, f, allow_unicode=True, default_flow_style=False)
                f.write("---\n\n")
                f.write(index_body)

        result_path = os.path.join(parent, safe_name) if parent else safe_name
        msg = f"Project folder '{result_path}' created."
        if warnings:
            msg += f"\n\nWarning: similar folder(s) already exist at this level: {', '.join(warnings)}. Verify this is intentional."
        tree = _folder_tree(knowledge_dir)
        msg += f"\n\nUpdated structure:\n{tree}"
        return json.dumps({"status": "success", "message": msg})

    @mcp.tool()
    def update_project(folder: str, description: str = "", scope: str = "") -> str:
        """
        Update the description and/or scope of an existing project folder.
        Edits the folder's _defaults.yaml in place.

        folder: relative path of the folder to update (e.g. 'Ganaghello' or 'Ganaghello/Operativo')
        description: new description text (leave empty to keep existing)
        scope: new default scope for files in this folder (leave empty to keep existing)
        """
        folder_path = os.path.join(knowledge_dir, folder)
        if not os.path.isdir(folder_path):
            return json.dumps({"status": "error", "message": f"Folder '{folder}' does not exist. Use list_projects to see available folders."})

        defaults_path = os.path.join(folder_path, '_defaults.yaml')
        defaults = {}
        if os.path.exists(defaults_path):
            try:
                with open(defaults_path) as f:
                    defaults = yaml.safe_load(f) or {}
            except Exception as e:
                return json.dumps({"status": "error", "message": f"Could not read _defaults.yaml: {e}"})

        if description:
            defaults["description"] = description
        if scope:
            defaults["scope"] = scope

        with open(defaults_path, 'w') as f:
            yaml.dump(defaults, f, allow_unicode=True, default_flow_style=False)

        return json.dumps({"status": "success", "message": f"Project '{folder}' updated.", "current": defaults})

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
        """
        Record a truly ephemeral, unnamed event or fleeting note (e.g. 'user seemed
        frustrated', 'quick log entry'). The file gets an auto-generated ID and lands
        in the knowledge root with no folder.

        DO NOT use this if:
        - the content has a clear subject or title → use create_node
        - the note belongs in a project folder → use create_node with folder=
        - the content is a goal or task → use create_goal / create_task

        When in doubt, prefer create_node.
        """
        obs_id = f"Obs_{uuid.uuid4().hex[:8]}"
        frontmatter = {"type": "Observation", "scope": scope}
        try:
            write_markdown(obs_id, frontmatter, content)
            return f"Observation recorded as {obs_id}.md in scope '{scope}'."
        except Exception as e:
            return f"Error recording observation: {e}"

    @mcp.tool()
    def create_node(name: str, content: str, node_type: str = "Node",
                    scope: str = "Public", links: str = "", folder: str = "",
                    relations: str = "") -> str:
        """
        Create a named knowledge node — a persistent, referenceable concept in memory.
        This is the DEFAULT tool for storing information. Use it for people, projects,
        topics, ideas, notes, or any content with a clear subject — including simple
        notes that belong in a project folder. Use add_observation only for truly
        ephemeral, unnamed events.

        name: meaningful identifier (e.g. 'Progetto Mnemosyne', 'Giorgio', 'Machine Learning')
        content: body of the node in markdown
        node_type: 'Node' (default), 'Reference' (evergreen, never decays), 'Goal', 'Task'
        scope: 'Public' (default) or 'Private'
        links: comma-separated node names for untyped wikilinks (e.g. 'Progetto Alpha,Giorgio')
        folder: relative path of an existing project folder (e.g. 'Ganaghello' or 'Ganaghello/Operativo')
        relations: typed relationships as 'Target:TYPE' pairs (e.g. 'Ganaghello:PART_OF,Giorgio:MANAGES')
                   valid types: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A
        """
        frontmatter = {"type": node_type, "scope": scope}
        if relations:
            frontmatter["relations"] = _parse_relations(relations)
        wikilinks = ""
        if links:
            targets = [l.strip() for l in links.split(",") if l.strip()]
            wikilinks = "\n\n" + " ".join(f"[[{t}]]" for t in targets)
        body = f"# {name}\n\n{content}{wikilinks}"
        try:
            write_markdown(name, frontmatter, body, folder=folder)
            return json.dumps({"status": "success", "message": f"Node '{name}' created with type '{node_type}'."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def get_memory_briefing() -> str:
        """Get a briefing on currently active (hot) topics."""
        active_nodes = kuzu_mgr.get_active_nodes(threshold=0.5)
        if not active_nodes:
             return "The memory is currently resting. No active thoughts."
             
        active_nodes.sort(key=lambda x: x['activation_level'], reverse=True)
        hot_topics = [n['name'] for n in active_nodes if not n['name'].startswith("obs_")][:10]

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
        """Read the raw markdown file from the file system.

        Accepts either a bare node name or a relative path including
        subfolders, e.g. 'Sistema/Alfred/System Prompt Alfred 3.0'.
        The '.md' extension is optional.
        """
        content = read_markdown(name)
        if not content:
            return json.dumps({"error": f"File '{name}' not found"}, indent=2)
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
    def update_node(name: str, content: str = "", updates: str = "") -> str:
        """Update the body and/or frontmatter of an existing node (works for any type: Node, Goal, Task, Observation).

        name: name of the existing node to update
        content: new markdown body — replaces the existing body entirely (omit to leave unchanged)
        updates: JSON object of frontmatter fields to merge into the existing frontmatter
                 e.g. '{"status": "done", "deadline": "2026-06-01", "relations": [{"target": "X", "type": "PART_OF"}]}'
                 omit to leave frontmatter unchanged
        """
        path = find_file_recursive(name)
        if not path or not os.path.exists(path):
            return json.dumps({"status": "error", "message": f"Node '{name}' not found."})
        if not content and not updates:
            return json.dumps({"status": "error", "message": "Provide at least one of 'content' or 'updates'."})
        properties_dict = {}
        if updates:
            try:
                properties_dict = json.loads(updates)
            except json.JSONDecodeError:
                return json.dumps({"error": "The 'updates' argument must be valid JSON."})
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
            yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)', raw, re.DOTALL)
            if yaml_match:
                frontmatter = yaml.safe_load(yaml_match.group(1)) or {}
                existing_body = yaml_match.group(2)
            else:
                frontmatter = {}
                existing_body = raw
            for k, v in properties_dict.items():
                frontmatter[k] = v
            write_markdown(name, frontmatter, content if content else existing_body)
            return json.dumps({"status": "success", "message": f"Node '{name}' updated."})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def create_goal(name: str, description: str = "", deadline: str = "",
                    scopes: str = "Private,Public", folder: str = "", relations: str = "") -> str:
        """Creates a new high-level strategic Goal as a Markdown file.

        folder: relative path of an existing project folder (e.g. 'Ganaghello')
        relations: typed relationships as 'Target:TYPE' pairs (e.g. 'Progetto:PART_OF')
                   valid types: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A
        """
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        frontmatter = {"type": "Goal", "status": "active", "scope": scope_list[0]}
        if deadline: frontmatter["deadline"] = deadline
        if relations: frontmatter["relations"] = _parse_relations(relations)
        body = f"# {name}\n\n{description}"
        try:
            write_markdown(name, frontmatter, body, folder=folder)
            return json.dumps({"status": "success", "message": f"Goal '{name}' created."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def create_task(name: str, goal_name: str, description: str = "", deadline: str = "",
                    scopes: str = "Private,Public", folder: str = "", relations: str = "") -> str:
        """Creates an actionable Task and links it to an existing Goal via wikilinks.

        folder: relative path of an existing project folder (e.g. 'Ganaghello')
        relations: typed relationships beyond the goal link, as 'Target:TYPE' pairs
                   valid types: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A
        """
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        frontmatter = {"type": "Task", "status": "todo", "scope": scope_list[0]}
        if deadline: frontmatter["deadline"] = deadline
        if relations: frontmatter["relations"] = _parse_relations(relations)
        body = f"# {name}\n\n**Linked Goal:** [[{goal_name}]]\n\n{description}"
        try:
            write_markdown(name, frontmatter, body, folder=folder)
            return json.dumps({"status": "success", "message": f"Task '{name}' created and linked to '{goal_name}'."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def update_task_status(name: str, status: str) -> str:
        """Updates the status of a Task or Goal."""
        return update_knowledge_frontmatter(name, json.dumps({"status": status}))

    return mcp
