import logging
import time
import datetime
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
        config = config or {}
        self.interval = config.get("gardener", {}).get("interval_seconds", 3600)
        self.threshold = config.get("gardener", {}).get("similarity_threshold", 0.85)
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
        logger.info("Gardener finished cycle.")

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
        Scans for Tasks with deadlines and boosts them if approaching or overdue.
        """
        logger.info("Gardener checking deadlines...")
        nodes = self.gm.get_all_nodes()
        now = datetime.now()
        
        for node in nodes:
            if "Task" in node['labels']:
                props = node.get('props', {})
                deadline_str = props.get('deadline')
                status = props.get('status', 'todo')
                
                if deadline_str and status != 'done':
                    try:
                        # Assuming ISO format for simplicity, or flexible parsing in real impl
                        # For this MVP, we'll try basic ISO
                        deadline = datetime.fromisoformat(deadline_str)
                        delta = deadline - now
                        
                        # Case 1: Overdue
                        if delta.total_seconds() < 0:
                            # Boost significantly to grab attention
                            self.am.stimulate([node['name']], boost_amount=0.8)
                            logger.info(f"Task '{node['name']}' is OVERDUE. Boosted.")
                            
                        # Case 2: Approaching (within 24 hours)
                        elif delta.total_seconds() < 86400:
                            self.am.stimulate([node['name']], boost_amount=0.5)
                            logger.info(f"Task '{node['name']}' is due soon. Boosted.")
                            
                    except ValueError:
                        logger.warning(f"Could not parse deadline '{deadline_str}' for node '{node['name']}'")

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
        Scans all nodes, compares names/concepts using simple string similarity.
        Create MAYBE_SAME_AS edges.
        """
        nodes = self.gm.get_all_nodes()
        # Exclude Observation nodes and ensure unique names list for comparison
        node_names = sorted(list(set(n['name'] for n in nodes if "Observation" not in n['labels'])))
        
        # O(N^2) comparison - acceptable for small personal graphs, 
        # but should be optimized (blocking or vector search) for production.
        
        for i in range(len(node_names)):
            for j in range(i + 1, len(node_names)):
                name_a = node_names[i]
                name_b = node_names[j]

                # Simple string/levenshtein check for MVP
                # In real life, ask LLM: "Are these the same?"
                if self._is_similar(name_a, name_b):
                    self.gm.add_edge(name_a, name_b, "MAYBE_SAME_AS", weight=0.0)
                    logger.info(f"Gardener marked {name_a} and {name_b} as potential duplicates.")

    def _is_similar(self, a, b):
        # 1. Fast Heuristic
        a_norm = a.lower().strip()
        b_norm = b.lower().strip()
        
        if a_norm == b_norm: return True
        
        # Substring match (e.g., "Python" vs "Python 3")
        heuristic = False
        if a_norm in b_norm or b_norm in a_norm:
            heuristic = True
            
        # Basic prefix/suffix overlap
        if len(a_norm) > 4 and len(b_norm) > 4:
            if a_norm[:4] == b_norm[:4]:
                heuristic = True

        if heuristic:
            return True
            
        # 2. LLM Deep Check (only if heuristic fails but names have some length)
        # We don't want to call LLM for every single pair if they are totaly different.
        # But for MVP let's be thorough if they are at least 3 chars.
        if len(a) > 2 and len(b) > 2:
             logger.info(f"Gardener asking LLM to compare '{a}' and '{b}'...")
             return self.llm.compare_entities(a, b)

        return False
