"""System Tray Service (v2.9.5) — Unblockable Notification Integration via pystray"""

import logging
import threading
import io
from typing import Optional, Callable

log = logging.getLogger(__name__)


class SystemTrayService:
    """System tray icon and notification service (v2.9.5)

    Having a System Tray Icon makes Windows recognize the process as an active
    desktop application, which unlocks permission to show notifications even
    when the app is minimized or in the background.

    This bypasses AUMID registry issues and portable .exe restrictions.
    """

    def __init__(self, app_name: str = "QuickNote"):
        """Initialize system tray service

        Args:
            app_name: Name of the application for tray icon
        """
        self.app_name = app_name
        self.icon = None
        self.is_running = False
        self.on_click_callback = None
        self._try_init_pystray()

    def _try_init_pystray(self):
        """Try to initialize pystray library"""
        try:
            import pystray
            from PIL import Image
            self.pystray = pystray
            self.PIL_Image = Image
            self.has_pystray = True
            log.info("[TrayService] pystray available for system tray notifications")
        except ImportError:
            log.warning("[TrayService] pystray not available, using fallback")
            self.pystray = None
            self.PIL_Image = None
            self.has_pystray = False

    def create_icon(self) -> bool:
        """Create system tray icon (should be called from main thread)

        Returns:
            True if icon created successfully, False otherwise
        """
        if not self.has_pystray:
            log.warning("[TrayService] pystray not available, cannot create icon")
            return False

        try:
            # Create a simple colored image for the tray icon (16x16 pixels)
            # Use blue color (#4A90E2 - QuickNote brand color)
            image = self.PIL_Image.new('RGB', (16, 16), color=(74, 144, 226))

            # Create menu items
            menu = self.pystray.Menu(
                self.pystray.MenuItem("Show", self._on_show_clicked),
                self.pystray.MenuItem("Hide", self._on_hide_clicked),
                self.pystray.MenuItem("Exit", self._on_exit_clicked),
            )

            # Create tray icon
            self.icon = self.pystray.Icon(
                name=self.app_name,
                icon=image,
                title=self.app_name,
                menu=menu
            )

            log.info("[TrayService] System tray icon created")
            return True

        except Exception as e:
            log.warning(f"[TrayService] Failed to create tray icon: {e}")
            return False

    def run_icon(self):
        """Run the tray icon (blocks until icon is stopped)

        Should be called from a background thread
        """
        if not self.icon:
            log.warning("[TrayService] Icon not created, cannot run")
            return

        try:
            self.is_running = True
            self.icon.run()
        except Exception as e:
            log.error(f"[TrayService] Icon run failed: {e}")
        finally:
            self.is_running = False

    def start_icon_thread(self):
        """Start tray icon in background thread

        Returns:
            True if started successfully, False otherwise
        """
        if not self.create_icon():
            return False

        try:
            thread = threading.Thread(target=self.run_icon, daemon=True)
            thread.start()
            log.info("[TrayService] Tray icon thread started")
            return True
        except Exception as e:
            log.error(f"[TrayService] Failed to start icon thread: {e}")
            return False

    def show_notification(self, title: str, message: str = None, on_click: Callable = None) -> bool:
        """Show system tray notification (v2.9.5 - Unblockable)

        Having the tray icon running makes Windows allow these notifications
        even for portable .exe files without AUMID registry entry.

        Args:
            title: Notification title
            message: Notification message
            on_click: Optional callback when notification is clicked

        Returns:
            True if notification shown successfully, False otherwise
        """
        try:
            self.on_click_callback = on_click

            if self.has_pystray and self.icon and self.is_running:
                try:
                    # Use pystray's built-in notification (if available)
                    msg = message if message else "Reminder triggered"

                    def show_in_thread():
                        try:
                            # pystray.Icon has notify() method for system notifications
                            # This uses Windows native tray balloon notification
                            if hasattr(self.icon, 'notify'):
                                self.icon.notify(msg, title)
                            log.info(f"[TrayService] Notification shown: {title}")
                        except Exception as e:
                            log.warning(f"[TrayService] notify() failed: {e}")

                    thread = threading.Thread(target=show_in_thread, daemon=True)
                    thread.start()
                    return True

                except Exception as e:
                    log.warning(f"[TrayService] Tray notification failed: {e}")
                    return False

            log.warning("[TrayService] Tray icon not available, using fallback")
            return False

        except Exception as e:
            log.error(f"[TrayService] Failed to show notification: {e}")
            return False

    def stop_icon(self):
        """Stop the tray icon"""
        try:
            if self.icon:
                self.icon.stop()
                log.info("[TrayService] Tray icon stopped")
        except Exception as e:
            log.warning(f"[TrayService] Failed to stop icon: {e}")

    def _on_show_clicked(self, icon, item):
        """Tray menu: Show app"""
        if self.on_click_callback:
            try:
                self.on_click_callback()
            except Exception as e:
                log.warning(f"[TrayService] Show callback failed: {e}")

    def _on_hide_clicked(self, icon, item):
        """Tray menu: Hide app"""
        log.info("[TrayService] Hide clicked (app-specific handler needed)")

    def _on_exit_clicked(self, icon, item):
        """Tray menu: Exit app"""
        log.info("[TrayService] Exit clicked")
        self.stop_icon()


# Global instance
_tray_service = None


def get_tray_service() -> SystemTrayService:
    """Get or create global tray service instance"""
    global _tray_service
    if _tray_service is None:
        _tray_service = SystemTrayService()
    return _tray_service


def initialize_tray_service() -> bool:
    """Initialize and start the tray service

    Should be called once at application startup

    Returns:
        True if tray service started successfully, False otherwise
    """
    service = get_tray_service()
    return service.start_icon_thread()
