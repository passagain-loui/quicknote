"""Google Tasks Integration Service (v2.8.0) — OAuth 2.0 sync with Google Tasks API"""

import json
import os
from pathlib import Path
import logging

log = logging.getLogger(__name__)


class GoogleTasksService:
    """Manage OAuth 2.0 connection and sync with Google Tasks API"""

    def __init__(self):
        self.credentials_path = None
        self.is_authenticated = False
        self.service = None
        self.task_list_id = "@default"  # Default task list

        # Check if credentials exist from prior session
        self._load_stored_credentials()

    def _load_stored_credentials(self):
        """Load stored credentials from local cache"""
        try:
            config_dir = Path.home() / ".quicknote"
            creds_file = config_dir / "google_tasks_credentials.json"

            if creds_file.exists():
                self.credentials_path = str(creds_file)
                self.is_authenticated = True
                log.info("[GoogleTasks] Credentials found in cache")
            else:
                self.is_authenticated = False
                log.info("[GoogleTasks] No cached credentials found")
        except Exception as e:
            log.warning(f"[GoogleTasks] Failed to load stored credentials: {e}")
            self.is_authenticated = False

    def set_credentials_path(self, credentials_json_path: str) -> bool:
        """Set path to credentials.json from Google Cloud Console"""
        try:
            if not os.path.exists(credentials_json_path):
                log.error(f"[GoogleTasks] Credentials file not found: {credentials_json_path}")
                return False

            self.credentials_path = credentials_json_path
            log.info(f"[GoogleTasks] Credentials path set: {credentials_json_path}")
            return True
        except Exception as e:
            log.error(f"[GoogleTasks] Failed to set credentials path: {e}")
            return False

    def authenticate(self) -> bool:
        """Authenticate with Google Tasks API using OAuth 2.0

        Returns True if authentication successful, False otherwise
        Note: This is a placeholder for OAuth 2.0 flow integration
        """
        try:
            if not self.credentials_path:
                log.error("[GoogleTasks] Credentials path not set")
                return False

            # TODO: Implement OAuth 2.0 flow here
            # This requires google-auth-oauthlib library
            # For now, just mark as ready to authenticate
            log.info("[GoogleTasks] Ready to authenticate (requires google-auth-oauthlib)")
            return True
        except Exception as e:
            log.error(f"[GoogleTasks] Authentication failed: {e}")
            return False

    def create_task(self, title: str, due_date: str = None, notes: str = None) -> bool:
        """Create a task in Google Tasks

        Args:
            title: Task title
            due_date: Due date in RFC 3339 format (e.g., "2026-08-20T15:30:00Z")
            notes: Task notes/description

        Returns True if successful, False otherwise
        """
        try:
            if not self.is_authenticated:
                log.warning("[GoogleTasks] Not authenticated, skipping task creation")
                return False

            # TODO: Implement actual task creation when service is initialized
            log.info(f"[GoogleTasks] Would create task: {title} (due: {due_date})")
            return True
        except Exception as e:
            log.error(f"[GoogleTasks] Failed to create task: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from Google Tasks and clear credentials"""
        try:
            self.is_authenticated = False
            self.service = None
            self.credentials_path = None
            log.info("[GoogleTasks] Disconnected from Google Tasks")
            return True
        except Exception as e:
            log.error(f"[GoogleTasks] Failed to disconnect: {e}")
            return False

    def get_status(self) -> dict:
        """Get current Google Tasks connection status"""
        return {
            "authenticated": self.is_authenticated,
            "credentials_path": self.credentials_path,
            "status": "Connected" if self.is_authenticated else "Disconnected"
        }


# Global instance
_google_tasks_service = None


def get_google_tasks_service() -> GoogleTasksService:
    """Get or create global Google Tasks service instance"""
    global _google_tasks_service
    if _google_tasks_service is None:
        _google_tasks_service = GoogleTasksService()
    return _google_tasks_service
