"""Windows Native Notifications (v2.9.4) — win10toast_click + Click Callbacks + System Tray Integration"""

import logging
import threading
import platform
import os
from pathlib import Path

log = logging.getLogger(__name__)


class WindowsNotificationService:
    """Send Windows native toast notifications with click callback support (v2.9.4)"""

    def __init__(self):
        self.on_click_callback = None
        # v2.8.4: Register AUMID BEFORE any notification attempt
        self._register_aumid()
        self._try_init_win10toast_click()

    def _register_aumid(self):
        """v2.8.3: Register Application User Model ID with Windows for proper notification delivery"""
        try:
            import ctypes
            aumid = 'PassagainP.QuickNote.v2.9.4'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(aumid)
            log.info(f"[Notification] AUMID registered: {aumid}")
        except Exception as e:
            log.warning(f"[Notification] Failed to register AUMID: {e}")

    def _try_init_win10toast_click(self):
        """v2.9.4: Try to import win10toast_click library (supports click callbacks)"""
        try:
            # Try win10toast_click first (has click support)
            from win10toast_click import ToastNotifier
            self.notifier = ToastNotifier()
            self.has_toast_click = True
            self.has_win10toast = True
            log.info("[Notification] win10toast_click available (click-aware notifications)")
        except ImportError:
            try:
                # Fallback to standard win10toast
                from win10toast import ToastNotifier
                self.notifier = ToastNotifier()
                self.has_toast_click = False
                self.has_win10toast = True
                log.info("[Notification] win10toast available (standard notifications)")
            except ImportError:
                log.warning("[Notification] No toast library available, using fallback")
                self.notifier = None
                self.has_toast_click = False
                self.has_win10toast = False

    def show_reminder_notification(self, note_title: str, note_content: str = None,
                                  on_click=None, duration: int = 8) -> bool:
        """Show Windows native reminder notification with click callback (v2.9.4)

        Args:
            note_title: Title of the note (notification title)
            note_content: Note content preview (notification message, optional)
            on_click: Callback function when notification is clicked
            duration: Duration in seconds to show notification (default 8)

        Returns True if notification shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            # v2.9.4: Priority 1: Try win10toast_click (click-aware)
            if self.has_toast_click and self.notifier:
                try:
                    return self._show_win10toast_click_notification(note_title, note_content, duration)
                except Exception as e:
                    log.warning(f"[Notification] win10toast_click failed: {e}, trying standard toast...")

            # Priority 2: Try standard win10toast
            if self.has_win10toast and self.notifier:
                try:
                    return self._show_win10toast_notification(note_title, note_content, duration)
                except Exception as e:
                    log.warning(f"[Notification] win10toast failed: {e}, trying Shell fallback...")

            # Priority 3: Windows Shell Notification
            try:
                result = self._show_shell_notification(note_title, note_content)
                if result:
                    return True
            except Exception as e:
                log.warning(f"[Notification] Shell notification failed: {e}, trying audio...")

            # Priority 4: Audio-only fallback
            log.warning("[Notification] Using audio-only fallback")
            return self._show_fallback_notification(note_title)

        except Exception as e:
            log.error(f"[Notification] Failed to show reminder notification: {e}")
            return False

    def _show_win10toast_click_notification(self, title: str, message: str = None, duration: int = 8) -> bool:
        """v2.9.4: Show Windows Toast via win10toast_click (with click callback support)"""
        try:
            title_str = title[:50] if title else "QuickNote Reminder"
            msg = message[:100] if message else "Reminder triggered"

            def show_in_thread():
                try:
                    # win10toast_click supports on_click callback
                    self.notifier.show_toast(
                        title=title_str,
                        msg=msg,
                        duration=duration,
                        threaded=False,
                        on_click=self.on_click_callback  # v2.9.4: Click support
                    )
                except Exception as e:
                    log.warning(f"[Notification] win10toast_click show failed: {e}")
                    raise

            thread = threading.Thread(target=show_in_thread, daemon=True)
            thread.start()
            log.info("[Notification] win10toast_click sent successfully with click support")
            return True

        except Exception as e:
            log.warning(f"[Notification] win10toast_click failed: {e}")
            return False

    def _show_win10toast_notification(self, title: str, message: str = None, duration: int = 8) -> bool:
        """v2.8.4: Show Windows Toast via standard win10toast (fallback)"""
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
        """v2.8.4: Show Windows Shell Notification (Tray Balloon) — Guaranteed visible"""
        try:
            import win32gui
            import win32con
            import time

            title_str = title[:256] if title else "QuickNote Reminder"
            msg = message[:256] if message else "Reminder triggered"

            class NotificationWindow:
                def __init__(self):
                    self.hwnd = None

            nw = NotificationWindow()

            try:
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

                flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
                nid = (nw.hwnd, 0, flags, win32con.WM_USER + 20,
                       win32gui.LoadIcon(0, win32con.IDI_APPLICATION), "QuickNote")
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)

                flags = win32gui.NIF_INFO
                nid = (nw.hwnd, 0, flags, win32con.WM_USER + 20,
                       win32gui.LoadIcon(0, win32con.IDI_INFORMATION), "QuickNote",
                       8000, 200, 1, title_str, msg)

                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)

                log.info(f"[Notification] Shell balloon shown: {title_str}")

                time.sleep(0.5)

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
            try:
                winsound.PlaySound("MailBeep", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                try:
                    winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception:
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
