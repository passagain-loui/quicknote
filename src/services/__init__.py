"""Services package — External service integrations (Google Tasks, Windows Notifications, etc.)"""

from .google_tasks import GoogleTasksService, get_google_tasks_service
from .notification import WindowsNotificationService, get_notification_service

__all__ = [
    "GoogleTasksService", "get_google_tasks_service",
    "WindowsNotificationService", "get_notification_service"
]
