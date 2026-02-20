import logging
import queue
import threading
from typing import Callable, Any

logger = logging.getLogger(__name__)

class EventBus:
    """
    A simple, thread-safe in-memory Event Bus for internal signaling.
    Allows decoupling of Core events from Plugin reactions.
    """
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._running = False
        self._thread = None

    def subscribe(self, event_type: str, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed callback to event: {event_type}")

    def publish(self, event_type: str, payload: Any):
        """
        Publishes an event to the queue for asynchronous processing.
        """
        self._queue.put((event_type, payload))
        logger.debug(f"Published event: {event_type}")

    def _process_events(self):
        while self._running:
            try:
                event_type, payload = self._queue.get(timeout=1.0)
                with self._lock:
                    callbacks = self._subscribers.get(event_type, [])
                    # Copy list to allow unsubscribing during callback
                    for callback in callbacks[:]:
                        try:
                            callback(payload)
                        except Exception as e:
                            logger.error(f"Error in EventBus callback for {event_type}: {e}")
                self._queue.task_done()
            except queue.Empty:
                continue

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._process_events, daemon=True)
            self._thread.start()
            logger.info("EventBus started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            logger.info("EventBus stopped.")
