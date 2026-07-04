from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
import uuid
import os
from datetime import datetime

from core.utils import resolve_safe_folder, atomic_write, render_markdown
from core.attention import thermal_rerank
from core.mcp_auth import scope_filter, require_privileged, assert_write, read_filter_grants
from core.authz import filter_by_read, territory_allows
from core import node_service


def create_mcp_server(kuzu_mgr, vector_store, am, gd, config, knowledge_dir):
    # Security Configuration for Remote Access
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["memory.borgonovo.org:*", "memory.borgonovo.org", "localhost:*", "localhost", "127.0.0.1:*", "127.0.0.1"],
        allowed_origins=["https://claude.ai", "https://memory.borgonovo.org", "http://localhost:*", "http://127.0.0.1:*"]
    )
    
    mcp = FastMCP("Mnemosyne-Memory", transport_security=security, streamable_http_path="/", stateless_http=True)

    # Helper functions — thin adapters over the shared core.node_service, so REST
    # and MCP can't drift apart (the drift caused the status-reset bug, 88aba32).
    def find_file_recursive(name: str):
        return node_service.find_node_file(knowledge_dir, name)

    def read_markdown(name: str):
        return node_service.read_markdown(knowledge_dir, name)

    def write_markdown(name: str, frontmatter: dict, body: str, folder: str = "", defaults: dict = None):
        """Upsert by name (merge frontmatter). Raises ValueError on an invalid
        folder for a new node; the calling tool turns it into a JSON error."""
        node_service.upsert(knowledge_dir, name, body, frontmatter,
                            folder=folder, defaults=defaults)

    def _parse_relations(relations_str: str, source: str = None) -> list:
        return node_service.parse_relations(relations_str, source)

    def _node_scope(name: str) -> str:
        return node_service.node_scope(knowledge_dir, name)

    def _territory_id(abs_path: str) -> str:
        return node_service.territory_id(knowledge_dir, abs_path)

    def _target_node_id(name: str, folder: str = "") -> str:
        return node_service.target_node_id(knowledge_dir, name, folder)

    @mcp.tool()
    def list_projects() -> str:
        """
        List all project folders in the knowledge base as an indented tree.
        Call this before create_project to check if a suitable folder already exists.
        """
        tree = node_service.folder_tree(knowledge_dir)
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
        try:
            folder_path = node_service.project_folder_path(knowledge_dir, name, parent)
        except ValueError as e:
            return json.dumps({"status": "error", "message": f"{e} Use list_projects to see available folders."})
        denied = assert_write(scope, _territory_id(folder_path))
        if denied:
            return denied
        try:
            res = node_service.create_project(knowledge_dir, name, description, scope, parent)
        except ValueError as e:
            tree = node_service.folder_tree(knowledge_dir)
            return json.dumps({"status": "error", "message": f"{e} Use it or choose a different name.\n\nCurrent structure:\n{tree}"})

        msg = f"Project folder '{res['result_path']}' created."
        if res["warnings"]:
            msg += f"\n\nWarning: similar folder(s) already exist at this level: {', '.join(res['warnings'])}. Verify this is intentional."
        msg += f"\n\nUpdated structure:\n{node_service.folder_tree(knowledge_dir)}"
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
        try:
            folder_path = resolve_safe_folder(knowledge_dir, folder)
            defaults = node_service.project_defaults(knowledge_dir, folder)
        except ValueError as e:
            return json.dumps({"status": "error", "message": f"{e} Use list_projects to see available folders."})

        territory = _territory_id(folder_path)
        denied = assert_write(defaults.get("scope", "Private"), territory)
        if denied:
            return denied
        if scope:
            denied = assert_write(scope, territory)
            if denied:
                return denied

        updated = node_service.update_project(knowledge_dir, folder, description, scope)
        return json.dumps({"status": "success", "message": f"Project '{folder}' updated.", "current": updated})

    @mcp.tool()
    def trigger_gardening_cycle() -> str:
        """
        Manually trigger a gardening cycle to apply temporal decay to network heat.
        """
        denied = require_privileged()
        if denied:
            return denied
        gd.run_once()
        return "Gardening cycle completed successfully. Memory network heat decayed."

    @mcp.tool()
    def query_knowledge(query: str, limit: int = 3) -> str:
        """Semantic search of the Mnemosyne knowledge base."""
        retrieval_cfg = config.get('retrieval', {})
        alpha = float(retrieval_cfg.get('rerank_alpha', 0.0))
        prefetch = max(limit * 2, int(retrieval_cfg.get('chroma_prefetch', 10)))

        candidates = vector_store.semantic_search(query, scopes=scope_filter(), limit=prefetch)
        candidates = filter_by_read(candidates, read_filter_grants(), "node_id")
        if not candidates:
            return f"No concepts matching '{query}' found in memory."

        reranked = thermal_rerank(candidates, kuzu_mgr, alpha=alpha)

        output = ""
        for r in reranked[:limit]:
            display = r['name']
            node_id = r.get('node_id', r['name'])
            content = read_markdown(node_id)
            if content:
                output += f"### FILE: {display}.md (score: {r['score']:.3f})\n```markdown\n{content}\n```\n\n"
                am.record_interaction(node_id, interaction_type="mcp_query")
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
        denied = assert_write(scope, _target_node_id(obs_id))
        if denied:
            return denied
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
        try:
            target_id = _target_node_id(name, folder)
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})
        denied = assert_write(scope, target_id)
        if denied:
            return denied
        frontmatter = {"type": node_type, "scope": scope}
        if relations:
            frontmatter["relations"] = _parse_relations(relations, source="user")
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
        sf = scope_filter()
        rg = read_filter_grants()
        active_nodes = kuzu_mgr.get_active_nodes(threshold=0.5, scopes=sf)
        active_nodes = filter_by_read(active_nodes, rg, "name")
        if not active_nodes:
             return "The memory is currently resting. No active thoughts."

        active_nodes.sort(key=lambda x: x['activation_level'], reverse=True)
        hot_nodes = [n for n in active_nodes
                     if not n['name'].startswith("obs_") and "__obs_" not in n['name']][:10]

        briefing = "Current active internal thoughts (Hot Nodes):\n"
        for n in hot_nodes:
            node_id = n['name']
            display = n.get('display_name') or node_id
            content = read_markdown(node_id)
            preview = content[:150].replace('\n', ' ') + "..." if content else "File not found"
            briefing += f"- {display} (Context: {preview})\n"

        dormant_cfg = config.get("attention", {}).get("dormant", {})
        dormant_nodes = kuzu_mgr.get_dormant_nodes(
            scopes=sf,
            min_interactions=dormant_cfg.get("min_interactions", 5),
            days_node=dormant_cfg.get("days_node", 27),
            days_goal_task=dormant_cfg.get("days_goal_task", 30),
        )
        dormant_nodes = filter_by_read(dormant_nodes, rg, "name")
        if dormant_nodes:
            briefing += "\nDormienti (erano attivi, ora inattivi):\n"
            for n in dormant_nodes[:5]:
                display = n.get('display_name') or n['name']
                briefing += f"- {display} ({n['node_type']}, inattivo da {n['days_inactive']}gg)\n"
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
        denied = require_privileged()
        if denied:
            return denied
        rg = read_filter_grants()
        files_found = []
        for root, dirs, files in os.walk(knowledge_dir):
            for f in files:
                full = os.path.join(root, f)
                # A privileged but territory-confined key only sees its own tree.
                if rg is not None and not territory_allows(rg, _territory_id(full)):
                    continue
                files_found.append(os.path.relpath(full, knowledge_dir))
        return "\n".join(files_found)

    @mcp.tool()
    def inspect_file_raw(name: str) -> str:
        """Read the raw markdown file from the file system.

        Accepts either a bare node name or a relative path including
        subfolders, e.g. 'Sistema/Alfred/System Prompt Alfred 3.0'.
        The '.md' extension is optional.
        """
        denied = require_privileged()
        if denied:
            return denied
        # Territory check: a confined key can only inspect files in its read
        # tree, reported as not found otherwise so existence isn't leaked.
        rg = read_filter_grants()
        path = find_file_recursive(name)
        if rg is not None and (not path or not territory_allows(rg, _territory_id(path))):
            return json.dumps({"error": f"File '{name}' not found"}, indent=2)
        content = read_markdown(name)
        if not content:
            return json.dumps({"error": f"File '{name}' not found"}, indent=2)
        return content

    @mcp.tool()
    def forget_knowledge_node(name: str) -> str:
        """Completely erases a concept by deleting its Markdown file."""
        path = find_file_recursive(name)
        if not (path and os.path.exists(path)):
            return json.dumps({"status": "error", "message": f"File '{name}.md' not found."}, indent=2)
        denied = assert_write(_node_scope(name), _territory_id(path))
        if denied:
            return denied
        os.remove(path)
        return json.dumps({"status": "success", "message": f"File '{name}.md' deleted."}, indent=2)

    @mcp.tool()
    def update_knowledge_frontmatter(name: str, updates: str) -> str:
        """Updates the YAML frontmatter properties of an existing entity."""
        path = find_file_recursive(name)
        if not path or not os.path.exists(path):
            return json.dumps({"status": "error", "message": f"Entity '{name}' not found."})
        territory = _territory_id(path)
        denied = assert_write(_node_scope(name), territory)
        if denied:
            return denied
        try:
            properties_dict = json.loads(updates)
        except json.JSONDecodeError:
             return json.dumps({"error": "The 'updates' argument must be valid JSON."})
        if "scope" in properties_dict:
            denied = assert_write(properties_dict["scope"], territory)
            if denied:
                return denied
        try:
            node_service.update_node(knowledge_dir, name, frontmatter_updates=properties_dict)
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
        territory = _territory_id(path)
        denied = assert_write(_node_scope(name), territory)
        if denied:
            return denied
        properties_dict = {}
        if updates:
            try:
                properties_dict = json.loads(updates)
            except json.JSONDecodeError:
                return json.dumps({"error": "The 'updates' argument must be valid JSON."})
        if "scope" in properties_dict:
            denied = assert_write(properties_dict["scope"], territory)
            if denied:
                return denied
        try:
            node_service.update_node(knowledge_dir, name, content=content,
                                     frontmatter_updates=properties_dict)
            return json.dumps({"status": "success", "message": f"Node '{name}' updated."})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def create_goal(name: str, description: str = "", deadline: str = "", status: str = "",
                    scopes: str = "Private,Public", folder: str = "", relations: str = "") -> str:
        """Creates a new high-level strategic Goal as a Markdown file, or updates an
        existing one with the same name (upsert).

        folder: relative path of an existing project folder (e.g. 'Ganaghello')
        status: e.g. 'active', 'done'. Omit to leave unchanged on update
                (defaults to 'active' on creation only — never resets an
                existing Goal's status on a later call).
        relations: typed relationships as 'Target:TYPE' pairs (e.g. 'Progetto:PART_OF')
                   valid types: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A
        """
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        try:
            target_id = _target_node_id(name, folder)
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})
        denied = assert_write(scope_list[0], target_id)
        if denied:
            return denied
        frontmatter = {"type": "Goal", "scope": scope_list[0]}
        if status: frontmatter["status"] = status
        if deadline: frontmatter["deadline"] = deadline
        if relations: frontmatter["relations"] = _parse_relations(relations, source="user")
        body = f"# {name}\n\n{description}"
        try:
            write_markdown(name, frontmatter, body, folder=folder, defaults={"status": "active"})
            return json.dumps({"status": "success", "message": f"Goal '{name}' created."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def create_task(name: str, goal_name: str, description: str = "", deadline: str = "",
                    status: str = "", scopes: str = "Private,Public", folder: str = "",
                    relations: str = "") -> str:
        """Creates an actionable Task and links it to an existing Goal via wikilinks,
        or updates an existing Task with the same name (upsert).

        folder: relative path of an existing project folder (e.g. 'Ganaghello')
        status: e.g. 'todo', 'in_progress', 'done'. Omit to leave unchanged on
                update (defaults to 'todo' on creation only — never resets an
                existing Task's status on a later call).
        relations: typed relationships beyond the goal link, as 'Target:TYPE' pairs
                   valid types: BELONGS_TO, REQUIRES, MANAGES, PART_OF, RELATED_TO, IS_A
        """
        scope_list = [s.strip() for s in scopes.split(",")] if scopes else ["Private"]
        try:
            target_id = _target_node_id(name, folder)
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})
        denied = assert_write(scope_list[0], target_id)
        if denied:
            return denied
        frontmatter = {"type": "Task", "scope": scope_list[0]}
        if status: frontmatter["status"] = status
        if deadline: frontmatter["deadline"] = deadline
        # goal_name becomes a typed CONTRIBUTES_TO edge rather than an implicit
        # LINKED_TO wikilink in the body (R2).
        rels = _parse_relations(relations, source="user") if relations else []
        if goal_name:
            rels.append({"target": goal_name, "type": "CONTRIBUTES_TO", "source": "user"})
        if rels:
            frontmatter["relations"] = rels
        body = f"# {name}\n\n{description}"
        try:
            write_markdown(name, frontmatter, body, folder=folder, defaults={"status": "todo"})
            return json.dumps({"status": "success", "message": f"Task '{name}' created and linked to '{goal_name}'."})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    @mcp.tool()
    def update_task_status(name: str, status: str) -> str:
        """Updates the status of a Task or Goal."""
        return update_knowledge_frontmatter(name, json.dumps({"status": status}))

    return mcp
