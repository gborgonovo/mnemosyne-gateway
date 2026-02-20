import logging
import time
import threading
from core.knowledge_queue import KnowledgeQueue
from core.perception import PerceptionModule

logger = logging.getLogger(__name__)

class LearningWorker(threading.Thread):
    """
    Background worker that processes the KnowledgeQueue.
    Decouples LLM-heavy extraction from the HTTP request cycle.
    """

    def __init__(self, queue: KnowledgeQueue, perception: PerceptionModule):
        super().__init__(daemon=True)
        self.queue = queue
        self.perception = perception
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        logger.info("LearningWorker started.")
        while self.running:
            try:
                jobs = self.queue.get_pending_jobs()
                if not jobs:
                    time.sleep(5) # Wait for new jobs
                    continue

                for job in jobs:
                    if not self.running: break
                    
                    job_id = job["id"]
                    content = job["content"]
                    obs_name = job["obs_name"]
                    
                    logger.info(f"LearningWorker: Processing job {job_id} for {obs_name}")
                    
                    try:
                        # Perform the heavy lifting
                        self.perception.extract_and_integrate(content, obs_name)
                        self.queue.mark_done(job_id)
                        logger.info(f"LearningWorker: Job {job_id} completed successfully.")
                    except Exception as e:
                        logger.error(f"LearningWorker: Job {job_id} failed: {e}")
                        self.queue.mark_failed(job_id, str(e))
                        # Wait a bit before retrying or moving to next job
                        time.sleep(2)

            except Exception as e:
                logger.error(f"LearningWorker: Critical error in loop: {e}")
                time.sleep(10)

        logger.info("LearningWorker stopped.")
