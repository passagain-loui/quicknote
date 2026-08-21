"""Thread-Safe Notification Queue (v2.8.5) — Decouple Background Thread from Tkinter UI"""

import queue
import logging
from typing import Optional, Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """Notification message to pass through thread-safe queue"""
    note_id: str
    title: str
    content: str = None
    on_open: Optional[Callable] = None
    on_dismiss: Optional[Callable] = None


class NotificationQueue:
    """Thread-safe queue for notifications

    v2.8.5: Background threads put notification messages in queue,
    main Tkinter thread periodically checks queue and displays notifications.

    This prevents deadlock and GUI freeze issues that occur when background
    threads try to call Tkinter UI operations directly.
    """

    def __init__(self, maxsize: int = 100):
        """Initialize notification queue

        Args:
            maxsize: Maximum queue size (default 100 notifications)
        """
        self._queue = queue.Queue(maxsize=maxsize)
        self._processing = False

    def put_notification(self, message: NotificationMessage) -> bool:
        """Add notification to queue (non-blocking)

        Called from background threads (safe - thread-safe queue)

        Args:
            message: NotificationMessage to queue

        Returns:
            True if queued successfully, False if queue full
        """
        try:
            self._queue.put_nowait(message)
            log.debug(f"[Queue] Notification queued: {message.title}")
            return True
        except queue.Full:
            log.warning(f"[Queue] Notification queue full, dropped: {message.title}")
            return False
        except Exception as e:
            log.error(f"[Queue] Error queuing notification: {e}")
            return False

    def get_next_notification(self) -> Optional[NotificationMessage]:
        """Get next notification from queue (non-blocking)

        Called from main Tkinter thread via root.after()

        Returns:
            NotificationMessage if available, None if queue empty
        """
        try:
            message = self._queue.get_nowait()
            log.debug(f"[Queue] Notification dequeued: {message.title}")
            return message
        except queue.Empty:
            return None
        except Exception as e:
            log.error(f"[Queue] Error dequeuing notification: {e}")
            return None

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return self._queue.empty()

    def size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()


# Global notification queue instance
_notification_queue = None


def get_notification_queue() -> NotificationQueue:
    """Get or create global notification queue instance"""
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = NotificationQueue()
    return _notification_queue


def reset_notification_queue():
    """Reset notification queue (for testing)"""
    global _notification_queue
    _notification_queue = NotificationQueue()
