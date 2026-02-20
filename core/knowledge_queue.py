import json
import os
import uuid
from datetime import datetime
from pathlib import Path

class KnowledgeQueue:
    """
    Manages a persistent queue for background knowledge ingestion jobs.
    Stored as JSON files in data/queue/.
    """

    def __init__(self, data_dir: str = "data/queue"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, content: str, obs_name: str) -> str:
        """
        Adds a new job to the queue.
        Returns the job ID.
        """
        job_id = str(uuid.uuid4())
        job_data = {
            "id": job_id,
            "obs_name": obs_name,
            "content": content,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "attempts": 0,
            "last_error": None
        }
        
        self._save_job(job_id, job_data)
        return job_id

    def get_pending_jobs(self) -> list[dict]:
        """Returns a list of all pending jobs, sorted by creation date."""
        jobs = []
        for file in self.data_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    job = json.load(f)
                    if job.get("status") in ["pending", "failed"]:
                        # Retry only if not maxed out (e.g., 5 attempts)
                        if job.get("attempts", 0) < 5:
                            jobs.append(job)
            except Exception:
                continue
        
        return sorted(jobs, key=lambda x: x.get("created_at", ""))

    def mark_done(self, job_id: str):
        """Marks a job as successfully processed."""
        job = self._load_job(job_id)
        if job:
            job["status"] = "completed"
            job["completed_at"] = datetime.now().isoformat()
            self._save_job(job_id, job)

    def mark_failed(self, job_id: str, error: str):
        """Increments attempt count and marks as failed."""
        job = self._load_job(job_id)
        if job:
            job["status"] = "failed"
            job["attempts"] = job.get("attempts", 0) + 1
            job["last_error"] = error
            job["updated_at"] = datetime.now().isoformat()
            self._save_job(job_id, job)

    def _save_job(self, job_id: str, data: dict):
        file_path = self.data_dir / f"{job_id}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_job(self, job_id: str) -> dict:
        file_path = self.data_dir / f"{job_id}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
