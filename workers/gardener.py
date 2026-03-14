import logging
import time
import datetime
import os
import sys

# Add project root to path BEFORE importing local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from core.graph_manager import GraphManager
from butler.llm import LLMProvider

logger = logging.getLogger(__name__)

class Gardener:
    """
    Background worker for Graph Hygiene.
    Strategy: Timid Suggestion.
    """

    def __init__(self, graph_manager: GraphManager, llm: LLMProvider, attention_model=None, config: dict = None):
        self.gm = graph_manager
        self.llm = llm
        self.am = attention_model
        self.config = config or {}
        self.interval = self.config.get("gardener", {}).get("interval_seconds", 3600)
        self.threshold = self.config.get("gardener", {}).get("similarity_threshold", 0.85)
        self.last_decay = 0

    def run_once(self):
        """
        Executes one cycle of gardening.
        """
        logger.info("Gardener waking up...")
        # New: First, fix hard duplicates (nodes with the exact same name)
        self.sanitize_duplicates()
        
        self.apply_temporal_decay()
        # Find semantic duplicates (similar names)
        self.find_and_mark_duplicates()
        self.check_deadlines()
        self.check_dormant_projects()
        self.check_orphan_tasks()
        # New: Backfill embeddings if enabled
        self.backfill_embeddings()
        logger.info("Gardener finished cycle.")

    def check_dormant_projects(self):
        """
        Retrieves dormant projects and creates proactive insights for The Butler.
        """
        long_cfg = getattr(self, 'config', {}).get('longitudinal_analysis', {})
        if not long_cfg.get('enabled', True):
            return
            
        threshold = long_cfg.get('dormancy_threshold_days', 30)
        logger.info(f"Gardener checking for dormant projects (>{threshold} days)...")
        
        dormant_nodes = self.gm.get_dormant_projects(threshold_days=threshold, limit=5)
        for node in dormant_nodes:
            logger.info(f"Identified dormant project/goal: {node['name']}")
            # We stimulate it slightly so it appears in the active context as a "ghost" or proactive suggestion
            if self.am:
                 self.am.stimulate([node['name']], boost_amount=0.3)

    def check_orphan_tasks(self):
        """
        Finds Tasks that have no relationships and flags them as orphans.
        If a Task is explicitly marked with 'allow_orphan'=True, it is ignored.
        """
        logger.info("Gardener checking for orphan Tasks...")
        nodes = self.gm.get_orphan_tasks()
        for node in nodes:
            name = node['name']
            # We add a hidden property so the InitiativeEngine can pick it up
            # without constantly boosting it
            self.gm.update_node_properties(name, {"_is_orphan": True})
            logger.info(f"Gardener marked Task '{name}' as orphan for future briefing.")

    def sanitize_duplicates(self):
        """
        Hard names cleanup: finds nodes with EXACT same name and merges them automatically.
        This fixes issues where multiple nodes were created with the same name before MERGE was enforced.
        """
        logger.info("Gardener sanitizing duplicate names...")
        query = """
        MATCH (n)
        WHERE NOT "Observation" IN labels(n)
        WITH n.name as name, collect(id(n)) as ids, count(*) as count
        WHERE count > 1
        RETURN name, ids
        """
        with self.gm.driver.session() as session:
            results = session.run(query)
            for record in results:
                name = record['name']
                ids = record['ids']
                logger.info(f"Auto-merging {len(ids)} nodes named '{name}'")
                
                # Keep the first one, merge others into it
                keep_id = ids[0]
                for discard_id in ids[1:]:
                    self.gm.merge_nodes(keep_id, discard_id)

    def check_deadlines(self):
        """
        Scans for Tasks and Goals with deadlines and boosts them if approaching or overdue.
        Acts as the TimeWatcher component of Proactive Planning.
        """
        intentionality_cfg = getattr(self, 'config', {}).get('intentionality', {})
        if not intentionality_cfg.get('enabled', True) or not intentionality_cfg.get('time_watcher', True):
            return

        logger.info("Gardener checking deadlines (TimeWatcher)...")
        nodes = self.gm.get_all_nodes()
        now = datetime.now()
        
        deadline_boost = intentionality_cfg.get('deadline_boost', 0.8)
        warning_boost = intentionality_cfg.get('warning_boost', 0.5)

        for node in nodes:
            labels = node.get('labels', [])
            if "Task" in labels or "Goal" in labels:
                props = node.get('props', {})
                # Check for either 'deadline' (Goals) or 'due_date' (Tasks)
                deadline_str = props.get('deadline') or props.get('due_date')
                status = props.get('status', 'todo')
                
                # Active/todo/in_progress tasks should be checked
                if deadline_str and status not in ['done', 'completed', 'discarded']:
                    try:
                        # Handle basic ISO formats including Z UTC marker
                        clean_date_str = deadline_str.replace('Z', '+00:00')
                        deadline = datetime.fromisoformat(clean_date_str)
                        # Strip timezone for simple comparison if 'now' is naive
                        if deadline.tzinfo is not None:
                            now_aware = datetime.now(deadline.tzinfo)
                            delta = deadline - now_aware
                        else:
                            delta = deadline - now
                        
                        # Case 1: Overdue
                        if delta.total_seconds() < 0:
                            # Boost significantly to grab attention
                            self.am.stimulate([node['name']], boost_amount=deadline_boost)
                            logger.info(f"[{node['name']}] is OVERDUE. TimeWatcher applied massive boost.")
                            
                        # Case 2: Approaching (within 48 hours for goals, 24 for tasks)
                        elif ("Goal" in labels and delta.total_seconds() < 172800) or \
                             ("Task" in labels and delta.total_seconds() < 86400):
                            self.am.stimulate([node['name']], boost_amount=warning_boost)
                            logger.info(f"[{node['name']}] is due soon. TimeWatcher applied warning boost.")
                            
                    except ValueError:
                        logger.warning(f"Could not parse date '{deadline_str}' for node '{node['name']}'")

    def apply_temporal_decay(self):
        """
        Manually triggers a decay step in the attention model.
        """
        if self.am:
            logger.info("Gardener applying temporal decay...")
            self.am.apply_decay()
            self.last_decay = time.time()

    def find_and_mark_duplicates(self):
        """
        Finds semantic duplicates using Embeddings-First strategy.
        If embeddings are not enabled, uses robust string matching (Levenshtein/Jaccard)
        to minimize LLM calls.
        """
        logger.info("Gardener looking for semantic duplicates...")
        
        llm_cfg = getattr(self, 'config', {}).get('llm', {})
        emb_cfg = llm_cfg.get('embeddings', {})
        if emb_cfg.get('enabled', False):
            # 1. Embeddings-First Strategy (Fast & Semantic)
            # Fetch directly from DB nodes with high cosine similarity
            logger.info("Using vector similarity for duplicates...")
            pairs = self.gm.get_highly_similar_node_pairs(threshold=self.threshold, limit=20)
            
            for pair in pairs:
                name_a = pair['source']
                name_b = pair['target']
                score = pair['score']
                
                # Double check with LLM if they are just "related" or actually "the same"
                logger.info(f"Vector score {score:.2f} for '{name_a}' and '{name_b}'. Asking LLM for final confirmation...")
                if self.llm.compare_entities(name_a, name_b):
                    self.gm.add_edge(name_a, name_b, "MAYBE_SAME_AS", weight=0.0)
                    logger.info(f"Gardener marked {name_a} and {name_b} as potential duplicates.")
                
            # If embeddings are on, we skip the slow python loop for safety and scale.
            return
            
        # 2. String-Fallback Strategy (No Embeddings)
        # O(N^2) loop, but heavily protected by string distance
        nodes = self.gm.get_all_nodes()
        node_names = sorted(list(set(n['name'] for n in nodes if "Observation" not in n['labels'])))
        
        for i in range(len(node_names)):
            for j in range(i + 1, len(node_names)):
                name_a = node_names[i]
                name_b = node_names[j]

                # Robust string matching before asking LLM
                if self._is_similar(name_a, name_b):
                    self.gm.add_edge(name_a, name_b, "MAYBE_SAME_AS", weight=0.0)
                    logger.info(f"Gardener marked {name_a} and {name_b} as potential duplicates.")

    def _is_similar(self, a, b):
        import difflib
        import re
        
        a_norm = a.lower().strip()
        b_norm = b.lower().strip()
        
        if a_norm == b_norm: return True
        
        # 1. Technical ID / Hash Protection
        # If strings look like technical IDs (e.g. item_abc123), skip simple heuristics.
        # These must be a very high match (>95%) to be considered potential duplicates.
        tech_pattern = re.compile(r'^[a-z0-9_-]+_[a-z0-9]{8,}$', re.I)
        if tech_pattern.match(a_norm) or tech_pattern.match(b_norm):
            ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
            return ratio > 0.95

        # 2. Natural Language Heuristics
        # Substring match (e.g., "Python" vs "Python 3")
        if len(a_norm) > 3 and len(b_norm) > 3:
            if a_norm in b_norm or b_norm in a_norm:
                # If one is a substring of the other, we still verify with a ratio
                # to avoid cases like "cat" in "category"
                ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
                if ratio > 0.7:
                    return self.llm.compare_entities(a, b)
                    
        # 3. Strict String Distance Filter
        # Do not bother LLM if string ratio is low
        ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
        
        if ratio > 0.75 and len(a_norm) > 2 and len(b_norm) > 2:
             logger.info(f"String ratio {ratio:.2f} high enough. Asking LLM to compare '{a}' and '{b}'...")
             return self.llm.compare_entities(a, b)

        return False

    def backfill_embeddings(self):
        """
        Periodically checks for nodes without embeddings and generates them in small batches.
        Only runs if enable_embeddings is true in the config.
        """
        llm_cfg = getattr(self, 'config', {}).get('llm', {})
        emb_cfg = llm_cfg.get('embeddings', {})
        if not emb_cfg.get('enabled', False):
            return

        logger.info("Gardener checking for missing embeddings (Backfill)...")
        # Process in small batches to avoid timeouts or cost spikes
        nodes = self.gm.get_nodes_missing_embeddings(limit=10)
        
        if not nodes:
            logger.info("No nodes missing embeddings found.")
            return

        logger.info(f"Backfilling {len(nodes)} nodes...")
        for node in nodes:
            text_to_embed = node.get('text', '').strip()
            if not text_to_embed:
                text_to_embed = node.get('name', 'Unknown')
            
            logger.debug(f"Generating embedding for '{node['name']}'...")
            try:
                embedding = self.llm.embed(text_to_embed)
                if embedding:
                    self.gm.update_node_embedding(node['name'], embedding)
                    logger.info(f"Successfully updated embedding for '{node['name']}'")
                else:
                    logger.warning(f"Failed to generate embedding for '{node['name']}'")
            except Exception as e:
                logger.error(f"Error embedding node '{node['name']}': {e}")

if __name__ == "__main__":
    import os
    import sys
    import yaml
    
    # Setup standard logging for CLI use
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add project root to path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    from core.graph_manager import GraphManager
    from butler.llm import get_llm_provider
    from core.attention import AttentionModel

    def load_config():
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
        if not os.path.exists(config_path):
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml.template')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    logger.info("Starting Gardener manual cycle...")
    try:
        config = load_config()
        gm = GraphManager(
            config['graph']['uri'], 
            config['graph']['user'], 
            config['graph']['password']
        )
        llm = get_llm_provider(config)
        am = AttentionModel(gm, config=config.get('attention', {}))
        
        gardener = Gardener(gm, llm, attention_model=am, config=config)
        gardener.run_once()
    except Exception as e:
        logger.error(f"Gardener manual cycle failed: {e}")
        sys.exit(1)

