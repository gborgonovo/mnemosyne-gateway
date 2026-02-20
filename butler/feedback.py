import logging
from core.graph_manager import GraphManager

logger = logging.getLogger(__name__)

class FeedbackManager:
    """
    Manages user feedback on graph relationships to refine future initiatives.
    """

    def __init__(self, graph_manager: GraphManager):
        self.gm = graph_manager

    def record_feedback(self, source_name: str, target_name: str, score: int):
        """
        Records feedback for a specific relationship or connection suggestion.
        Score: +1 (Positive/Useful), -1 (Negative/Irrelevant).
        
        It creates or updates a 'FEEDBACK_ON' relationship from a (virtual) User node 
        or simply tags an existing relationship with a feedback score.
        
        For MVP, we will add/update a 'feedback_score' property on the DIRECT edge between source and target.
        """
        if source_name == target_name:
            return

        with self.gm.driver.session() as session:
            # Check if edge exists
            query_check = """
            MATCH (a {name: $source})-[r]-(b {name: $target})
            RETURN r
            """
            result = session.run(query_check, source=source_name, target=target_name).single()
            
            if result:
                # Update existing edge property (cumulative)
                query_update = """
                MATCH (a {name: $source})-[r]-(b {name: $target})
                SET r.feedback_score = coalesce(r.feedback_score, 0) + $score
                RETURN r.feedback_score as new_score
                """
                new_score = session.run(query_update, source=source_name, target=target_name, score=score).single()['new_score']
                logger.info(f"Feedback recorded for {source_name}<->{target_name}. New Score: {new_score}")
            else:
                # If no direct edge exists (it was a loose suggestion), we might create a specific 'SUGGESTED_CONNECTION' edge
                # or just log it for now. For the initiative engine to work, usually an edge exists (even if weak).
                logger.warning(f"No direct edge found between {source_name} and {target_name} to attach feedback.")
