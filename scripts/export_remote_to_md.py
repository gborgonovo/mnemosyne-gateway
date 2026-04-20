import requests
import json
import os
import yaml
import re
import shutil

TARGET_DIR = "/home/giorgio/Projects/mnemosyne-gateway/knowledge"
API_URL = "https://memory.borgonovo.org/graph/export"
API_KEY = "mnm_sk_master_197001"

def sanitize_filename(name):
    if not name: return "unnamed"
    name = re.sub(r'[^\w\s-]', '', name).strip()
    return name.replace(" ", "_").replace("__", "_")

def is_junk_name(name):
    return name.startswith("item_") or name.startswith("Node_") or name.startswith("Obs_")

def export_knowledge():
    # 1. Fetch Data
    print(f"Connecting to {API_URL}...")
    headers = {"X-API-Key": API_KEY}
    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return
        
    data = response.json().get("data", {})
    raw_nodes = data.get("nodes", [])
    raw_rels = data.get("relationships", [])
    
    # 2. Map IDs to Nodes and build Name->ID index
    nodes = {}
    id_to_human_name = {}
    
    # First pass: Determine the best "Human Name" for every node
    for rn in raw_nodes:
        nid = rn["id"]
        props = rn.get("properties", {})
        
        # Priority for name: property "title" -> property "name" -> raw "name" -> raw "id"
        human_name = props.get("title") or props.get("name") or rn.get("name") or f"Node_{nid}"
        
        # If the determined name is still a junk ID, keep it but we'll try to refine later
        id_to_human_name[nid] = human_name
        
        nodes[nid] = {
            "id": nid,
            "name": human_name,
            "labels": rn.get("labels", []),
            "properties": props,
            "parents": [], 
            "children": [], 
            "links": [],   
            "is_hub": False,
            "folded_observations": set()
        }

    # 3. Preparation: Identify potential targets for folding (Keyword Matching)
    obs_info = {}
    # We only fold into non-observation nodes that have "Human" names
    potential_targets = [n for n in nodes.values() if "Observation" not in n["labels"]]

    for nid, node in nodes.items():
        if "Observation" in node["labels"]:
            content = (node["properties"].get("content", "") or node["properties"].get("text", "") or node["properties"].get("descrizione", "") or "").strip()
            tags = [t.lower() for t in node["labels"] + node["properties"].get("tags", [])]
            timestamp = node["properties"].get("timestamp") or node["properties"].get("last_seen", "Unknown Time")
            
            obs_info[nid] = {
                "content": content,
                "timestamp": timestamp,
                "targets": set()
            }
            
            # Heuristic 1: Tags
            for t in tags:
                # Find node with matching human name
                for tnid, tnode in nodes.items():
                    if tnode["name"].lower() == t:
                        obs_info[nid]["targets"].add(tnid)
            
            # Heuristic 2: Content Keyword Matching
            if len(content) > 10:
                content_lower = content.lower()
                for tnode in potential_targets:
                    tname = tnode["name"]
                    if len(tname) < 4 or is_junk_name(tname): continue
                    if tname.lower() in content_lower:
                        obs_info[nid]["targets"].add(tnode["id"])

    # 4. Process Relationships
    for rr in raw_rels:
        source_id = rr.get("source")
        target_id = rr.get("target")
        rel_type = rr.get("type")
        
        if source_id in nodes and target_id in nodes:
            # RELATIONSHIP CLEANUP: Skip technical noise
            if rel_type == "MAYBE_SAME_AS": continue
            
            nodes[source_id]["links"].append({
                "target": nodes[target_id]["name"],
                "type": rel_type
            })
            
            if rel_type == "PART_OF":
                nodes[source_id]["parents"].append(target_id)
                nodes[target_id]["children"].append(source_id)
                nodes[target_id]["is_hub"] = True
            
            if rel_type == "MENTIONED_IN" and target_id in obs_info:
                obs_info[target_id]["targets"].add(source_id)

    # 5. Execute FOLDING
    for obs_id, info in obs_info.items():
        for target_id in info["targets"]:
            if target_id in nodes:
                nodes[target_id]["folded_observations"].add(obs_id)

    # Hub marking
    for nid, node in nodes.items():
        if "Project" in node["labels"] or "Goal" in node["labels"]:
            node["is_hub"] = True

    # 6. Clear and Prepare Directories
    if os.path.exists(TARGET_DIR):
        print(f"Clearing old knowledge in {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR)
    os.makedirs(TARGET_DIR, exist_ok=True)

    # 7. Write Files
    count = 0
    exported_obs_ids = set()

    for nid, node in nodes.items():
        labels = node["labels"]
        if "Observation" in labels: continue
            
        # Determine Folder Path based on metadata or parenthood
        # SEARCH FOR PROJECT CONTEXT in properties
        project_context = node["properties"].get("Project context") or node["properties"].get("project_context")
        
        folder_path = []
        if project_context:
            folder_path = [sanitize_filename(project_context)]
            if node["is_hub"]:
                folder_path.append(sanitize_filename(node["name"]))
        elif node["parents"]:
            parent_id = node["parents"][0]
            folder_path = [sanitize_filename(nodes[parent_id]["name"])]
            if node["is_hub"]:
                folder_path.append(sanitize_filename(node["name"]))
        elif node["is_hub"]:
            folder_path = [sanitize_filename(node["name"])]
        else:
            folder_path = ["General"]
            
        full_dest_dir = os.path.join(TARGET_DIR, *folder_path)
        os.makedirs(full_dest_dir, exist_ok=True)
        
        # Build Body
        body = f"# {node['name']}\n\n"
        
        props = node["properties"]
        content_keys = ["description", "descrizione", "summary", "context", "goal_description"]
        
        for ck in content_keys:
            if ck in props and props[ck] and str(props[ck]).strip():
                label = ck.capitalize().replace("_", " ")
                body += f"## {label}\n{props[ck]}\n\n"
        
        if node["folded_observations"]:
            sorted_obs_ids = sorted(list(node["folded_observations"]), key=lambda x: str(obs_info[x]["timestamp"]))
            body += "## Diario delle Osservazioni\n\n"
            for oid in sorted_obs_ids:
                o = obs_info[oid]
                if o["content"]:
                    body += f"### {o['timestamp']}\n{o['content']}\n\n"
                    exported_obs_ids.add(oid)
        
        if node["children"]:
            body += "## Sotto-obiettivi e Contenuti (MOC)\n"
            for cid in node["children"]:
                body += f"- [[{nodes[cid]['name']}]]\n"
            body += "\n"

        if node["links"]:
            body += "## Collegamenti Correlati\n"
            for link in node["links"]:
                body += f"- [[{link['target']}]] ({link['type']})\n"
            body += "\n"

        # Metadata
        frontmatter = {
            "uuid": nid,
            "type": labels[0] if labels else "Node",
            "tags": labels,
            "original_name": nodes[nid]["properties"].get("name") # Keep original ID as metadata
        }
        for k, v in props.items():
            if k in ["name", "embedding", "activation_level", "last_seen", "uuid", "id", "timestamp", "title"] or k in content_keys or k == "content":
                continue
            if isinstance(v, (str, int, float, bool)):
                frontmatter[k] = v

        filename = sanitize_filename(node["name"])
        filepath = os.path.join(full_dest_dir, f"{filename}.md")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("---\n")
                yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False)
                f.write("---\n\n")
                f.write(body)
            count += 1
        except Exception as e:
            print(f"Failed to write {filename}: {e}")

    # 8. True Orphans
    obs_count = 0
    obs_dir = os.path.join(TARGET_DIR, "Observations")
    os.makedirs(obs_dir, exist_ok=True)
    
    for nid, node in nodes.items():
        if "Observation" in node["labels"] and nid not in exported_obs_ids:
            content = obs_info[nid]["content"]
            if not content or len(content) < 5: continue
            body = f"# {node['name']}\n\n{content}\n"
            filepath = os.path.join(obs_dir, f"{sanitize_filename(node['name'])}.md")
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("---\n")
                    yaml.dump({"uuid": nid, "type": "Observation", "tags": node["labels"]}, f)
                    f.write("---\n\n")
                    f.write(body)
                obs_count += 1
            except Exception as e:
                print(f"Failed to write orphan obs {node['name']}: {e}")

    print(f"Export V6 (Human Renaming) Completed.")
    print(f"- {count} Files renamed to human titles and organized.")
    print(f"- {obs_count} Orphan observations remaining.")

if __name__ == "__main__":
    export_knowledge()
