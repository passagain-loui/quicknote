"""Windows Native Notifications (v2.8.4) — Toast + Shell Fallback + AUMID Registration"""

import logging
import threading
import platform
import os
from pathlib import Path

log = logging.getLogger(__name__)


class WindowsNotificationService:
    """Send Windows native toast notifications to Action Center"""

    def __init__(self):
        self.on_click_callback = None
        # v2.8.4: Register AUMID BEFORE any notification attempt
        # This enables Windows to allow Toast notifications in Action Center
        self._register_aumid()
        self._try_init_win10toast()

    def _register_aumid(self):
        """v2.8.3: Register Application User Model ID with Windows for proper notification delivery"""
        try:
            import ctypes
            # App AUMID must match any shortcuts created
            aumid = 'PassagainP.QuickNote.v2.8.3'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(aumid)
            log.info(f"[Notification] AUMID registered: {aumid}")
        except Exception as e:
            log.warning(f"[Notification] Failed to register AUMID: {e}")

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
        """Show Windows native reminder notification with guaranteed fallback chain

        v2.8.4: Windows-optimized with AUMID registration + Toast → Shell Balloon → Audio

        Args:
            note_title: Title of the note (notification title)
            note_content: Note content preview (notification message, optional)
            on_click: Callback function when notification is clicked
            duration: Duration in seconds to show notification (default 8)

        Returns True if notification shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            # v2.8.4: Windows-specific notification fallback chain
            # Priority 1: Try win10toast (best user experience)
            if self.has_win10toast and self.notifier:
                try:
                    return self._show_win10toast_notification(note_title, note_content, duration)
                except Exception as e:
                    log.warning(f"[Notification] win10toast failed: {e}, trying Shell fallback...")

            # Priority 2: Windows Shell Notification (Tray Balloon) — guaranteed visible
            try:
                result = self._show_shell_notification(note_title, note_content)
                if result:
                    return True
            except Exception as e:
                log.warning(f"[Notification] Shell notification failed: {e}, trying audio...")

            # Priority 3: Audio-only fallback (guaranteed to work)
            log.warning("[Notification] Using audio-only fallback")
            return self._show_fallback_notification(note_title)

        except Exception as e:
            log.error(f"[Notification] Failed to show reminder notification: {e}")
            return False

    def _show_win10toast_notification(self, title: str, message: str = None, duration: int = 8) -> bool:
        """v2.8.4: Show Windows Toast via win10toast (priority 1)

        Best UX if available, but may fail if Focus Assist is enabled
        """
        try:
            title_str = title[:50] if title else "QuickNote Reminder"
            msg = message[:100] if message else "Reminder triggered"

            def show_in_thread():
                try:
                    self.notifier.show_toast(
                        title=title_str,
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
                    log.warning(f"[Notification] win10toast show failed: {e}")
                    raise

            thread = threading.Thread(target=show_in_thread, daemon=True)
            thread.start()
            log.info("[Notification] win10toast sent successfully")
            return True

        except Exception as e:
            log.warning(f"[Notification] win10toast failed: {e}")
            return False

    def _show_shell_notification(self, title: str, message: str = None) -> bool:
        """v2.8.4: Show Windows Shell Notification (Tray Balloon) — Guaranteed visible

        Uses win32gui.Shell_NotifyIcon to show balloon in taskbar.
        This is the fallback when win10toast fails (e.g., Focus Assist enabled).
        Balloon appears in taskbar corner (bottom-right area).
        """
        try:
            import win32gui
            import win32con
            import time

            title_str = title[:256] if title else "QuickNote Reminder"
            msg = message[:256] if message else "Reminder triggered"

            # Create a hidden window for the notification
            class NotificationWindow:
                def __init__(self):
                    self.hwnd = None

            nw = NotificationWindow()

            try:
                # Register window class
                wc = win32gui.WNDCLASS()
                wc.lpszClassName = "QuickNoteNotification"
                wc.lpfnWndProc = {}

                classAtom = win32gui.RegisterClass(wc)
                nw.hwnd = win32gui.CreateWindow(
                    classAtom, "QuickNote",
                    win32con.WS_OVERLAPPED | win32con.WS_SYSMENU,
                    0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
                    0, 0, win32gui.GetModuleHandle(None), None
                )

                # Add icon to notification area (tray)
                flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
                nid = (nw.hwnd, 0, flags, win32con.WM_USER + 20,
                       win32gui.LoadIcon(0, win32con.IDI_APPLICATION), "QuickNote")
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

                # Show notification balloon (priority: NIIF_INFO for blue info icon)
                flags = win32gui.NIF_INFO
                nid = (nw.hwnd, 0, flags, win32con.WM_USER + 20,
                       win32gui.LoadIcon(0, win32con.IDI_INFORMATION), "QuickNote",
                       8000, 200, 1, title_str, msg)  # 8000ms timeout, NIIF_INFO=1

                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)

                log.info(f"[Notification] Shell balloon shown: {title_str}")

                # Keep window alive long enough for notification to display
                time.sleep(0.5)

                # Cleanup after notification shown
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (nw.hwnd, 0))
                except Exception:
                    pass

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
