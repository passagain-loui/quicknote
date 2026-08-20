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
        """Show Windows native reminder notification with fallback chain

        Args:
            note_title: Title of the note (notification title)
            note_content: Note content preview (notification message, optional)
            on_click: Callback function when notification is clicked
            duration: Duration in seconds to show notification (default 8)

        Returns True if notification shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            # v2.8.2: Try multiple notification methods with fallback chain
            # Method 1: win10toast
            if self.has_win10toast and self.notifier:
                try:
                    def show_win10toast_in_thread():
                        try:
                            title = note_title[:50] if note_title else "QuickNote Reminder"
                            msg = note_content[:100] if note_content else "Reminder triggered"

                            self.notifier.show_toast(
                                title=title,
                                msg=msg,
                                duration=duration,
                                threaded=False
                            )

                            # Execute callback if user clicked
                            if self.on_click_callback:
                                try:
                                    self.on_click_callback()
                                except Exception:
                                    pass
                        except Exception as e:
                            log.warning(f"[Notification] win10toast failed: {e}")
                            # Fall through to next method

                    thread = threading.Thread(target=show_win10toast_in_thread, daemon=True)
                    thread.start()
                    return True
                except Exception as e:
                    log.warning(f"[Notification] win10toast error: {e}")

            # Method 2: Windows Shell Notification (fallback)
            try:
                return self._show_shell_notification(note_title, note_content)
            except Exception as e:
                log.warning(f"[Notification] Shell notification failed: {e}")

            # Method 3: System MessageBox (last resort)
            log.warning("[Notification] Using final fallback notification method")
            return self._show_fallback_notification(note_title)

        except Exception as e:
            log.error(f"[Notification] Failed to show reminder notification: {e}")
            return False

    def _show_shell_notification(self, title: str, message: str = None) -> bool:
        """v2.8.2: Show Windows Shell notification using win32gui

        This is a fallback when win10toast doesn't work (e.g., Focus Assist enabled)
        """
        try:
            import win32gui
            import win32con

            # Create a hidden window for the notification
            class NotificationWindow:
                def __init__(self):
                    self.hwnd = None

            nw = NotificationWindow()

            # Register window class
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "QuickNoteNotification"
            wc.lpfnWndProc = {}

            try:
                classAtom = win32gui.RegisterClass(wc)
                nw.hwnd = win32gui.CreateWindow(
                    classAtom, "QuickNote",
                    win32con.WS_OVERLAPPED | win32con.WS_SYSMENU,
                    0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
                    0, 0, win32gui.GetModuleHandle(None), None
                )

                # Show notification using Shell_NotifyIcon
                flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
                nid = (nw.hwnd, 0, flags, win32con.WM_USER + 20, win32gui.LoadIcon(0, win32con.IDI_APPLICATION), "QuickNote")
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

                # Update with our notification
                nid = (nw.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20,
                       win32gui.LoadIcon(0, win32con.IDI_INFORMATION), "QuickNote",
                       200, 200, (title[:256] if title else "Reminder"))
                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)

                log.info("[Notification] Shell notification shown successfully")
                return True
            except Exception as e:
                log.warning(f"[Notification] Shell_NotifyIcon failed: {e}")
                return False

        except ImportError:
            log.warning("[Notification] win32gui not available, cannot use Shell notification")
            return False
        except Exception as e:
            log.error(f"[Notification] Shell notification error: {e}")
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
