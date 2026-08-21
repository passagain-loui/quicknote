"""Win32 Native MessageBox Service (v2.9.6) — Unblockable Native Dialog (Nuclear Option)"""

import logging
import threading
import ctypes
from typing import Optional, Callable

log = logging.getLogger(__name__)


class Win32MessageBoxService:
    """Win32 native MessageBox — lowest-level Windows dialog (cannot be blocked)

    v2.9.6: Nuclear option when all other notification methods fail.
    MessageBox is a native Windows dialog at the OS level that:
    - Cannot be blocked by Windows notification restrictions
    - Always appears on screen regardless of permissions
    - Always on top of all other windows
    - Forces user interaction (requires explicit OK click)
    """

    # MessageBox button and icon flags
    MB_OK = 0x00000000
    MB_OKCANCEL = 0x00000001
    MB_YESNO = 0x00000004
    MB_YESNOCANCEL = 0x00000003

    MB_ICONINFORMATION = 0x00000040
    MB_ICONEXCLAMATION = 0x00000030
    MB_ICONQUESTION = 0x00000020
    MB_ICONSTOP = 0x00000010

    # Window display flags
    MB_TOPMOST = 0x00040000        # Always on top
    MB_SETFOREGROUND = 0x00010000  # Set as foreground window
    MB_SYSTEMMODAL = 0x00001000    # System modal (most intrusive)

    def __init__(self):
        """Initialize Win32 MessageBox service"""
        self.on_click_callback = None

    def show_messagebox(self, title: str, message: str = None, on_click: Callable = None) -> bool:
        """Show Win32 native MessageBox (unblockable, nuclear option)

        v2.9.6: This is the absolute lowest-level Windows dialog that
        cannot be blocked by OS-level notification restrictions.

        Args:
            title: MessageBox title
            message: MessageBox message
            on_click: Optional callback when user clicks OK

        Returns:
            True if shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            msg = message if message else "Reminder triggered"
            title_str = title if title else "QuickNote Reminder"

            # Combine flags for maximum intrusiveness
            # TOPMOST + SETFOREGROUND + SYSTEMMODAL ensures it appears
            flags = (
                self.MB_OK |
                self.MB_ICONINFORMATION |
                self.MB_TOPMOST |
                self.MB_SETFOREGROUND |
                self.MB_SYSTEMMODAL
            )

            def show_in_thread():
                """Run MessageBox in separate thread (doesn't block Tkinter)"""
                try:
                    # Use parent window = 0 (desktop) for system-level dialog
                    result = ctypes.windll.user32.MessageBoxW(
                        0,  # hwndParent = desktop
                        msg,  # lpText = message
                        title_str,  # lpCaption = title
                        flags  # uType = flags (OK + Info Icon + Topmost + Foreground + Modal)
                    )

                    log.info(f"[Win32MessageBox] MessageBox shown: {title_str} (result={result})")

                    # Execute callback after user clicks OK
                    if self.on_click_callback:
                        try:
                            self.on_click_callback()
                        except Exception as e:
                            log.warning(f"[Win32MessageBox] Callback failed: {e}")

                except Exception as e:
                    log.error(f"[Win32MessageBox] MessageBox failed: {e}")

            # Run in daemon thread (non-blocking)
            thread = threading.Thread(target=show_in_thread, daemon=True)
            thread.start()

            log.info("[Win32MessageBox] MessageBox thread started")
            return True

        except Exception as e:
            log.error(f"[Win32MessageBox] Failed to show MessageBox: {e}")
            return False


# Global instance
_win32_service = None


def get_win32_messagebox_service() -> Win32MessageBoxService:
    """Get or create global Win32 MessageBox service instance"""
    global _win32_service
    if _win32_service is None:
        _win32_service = Win32MessageBoxService()
    return _win32_service
