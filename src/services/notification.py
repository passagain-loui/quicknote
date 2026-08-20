"""Windows Native Toast Notification Service (v2.8.1) — Replace Tkinter Toast with OS notifications"""

import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)


class WindowsNotificationService:
    """Send Windows native toast notifications to Action Center"""

    def __init__(self):
        self.on_click_callback = None
        self._try_init_win10toast()

    def _try_init_win10toast(self):
        """Try to import win10toast library"""
        try:
            from win10toast import ToastNotifier
            self.notifier = ToastNotifier()
            self.has_win10toast = True
            log.info("[Notification] win10toast available for native notifications")
        except ImportError:
            log.warning("[Notification] win10toast not available, using fallback")
            self.notifier = None
            self.has_win10toast = False

    def show_reminder_notification(self, note_title: str, note_content: str = None,
                                  on_click=None, duration: int = 8) -> bool:
        """Show Windows native reminder notification

        Args:
            note_title: Title of the note (notification title)
            note_content: Note content preview (notification message, optional)
            on_click: Callback function when notification is clicked
            duration: Duration in seconds to show notification (default 8)

        Returns True if notification shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            # Use win10toast if available
            if self.has_win10toast and self.notifier:
                try:
                    # Show notification in background thread to avoid blocking UI
                    def show_in_thread():
                        try:
                            # Truncate title/content for readability
                            title = note_title[:50] if note_title else "QuickNote Reminder"
                            msg = note_content[:100] if note_content else "Reminder triggered"

                            # Show toast (win10toast blocks briefly, so do it in thread)
                            self.notifier.show_toast(
                                title=title,
                                msg=msg,
                                duration=duration,
                                threaded=False
                            )

                            # Execute callback if user clicked
                            if self.on_click_callback:
                                self.on_click_callback()
                        except Exception as e:
                            log.warning(f"[Notification] Failed to show win10toast: {e}")

                    # Run in daemon thread so it doesn't block UI
                    thread = threading.Thread(target=show_in_thread, daemon=True)
                    thread.start()
                    return True
                except Exception as e:
                    log.error(f"[Notification] win10toast error: {e}")
                    return False
            else:
                # Fallback: Use system MessageBox (not ideal but better than nothing)
                log.warning("[Notification] Using fallback notification method")
                return self._show_fallback_notification(note_title)

        except Exception as e:
            log.error(f"[Notification] Failed to show reminder notification: {e}")
            return False

    def _show_fallback_notification(self, title: str) -> bool:
        """Fallback notification using winsound only (no visual notification)"""
        try:
            import winsound
            # Just play audio without visual notification
            try:
                winsound.PlaySound("MailBeep", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                winsound.MessageBeep(winsound.MB_OK)
            return True
        except Exception as e:
            log.error(f"[Notification] Fallback notification failed: {e}")
            return False

    def play_notification_sound(self) -> bool:
        """Play notification sound (Ding-Dong chime)"""
        try:
            import winsound
            # Primary: Use MailBeep for soft Ding-Dong tone
            try:
                winsound.PlaySound("MailBeep", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                # Fallback: System notification sound
                try:
                    winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception:
                    # Last resort: Generic beep
                    winsound.MessageBeep(winsound.MB_OK)
            return True
        except Exception as e:
            log.error(f"[Notification] Failed to play sound: {e}")
            return False


# Global instance
_notification_service = None


def get_notification_service() -> WindowsNotificationService:
    """Get or create global notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = WindowsNotificationService()
    return _notification_service
