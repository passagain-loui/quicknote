"""Settings Window - Theme, Alpha, Hotkey settings, About"""

import tkinter as tk
from tkinter import ttk
import logging
from .theme import Theme
from ..core.constants import APP_NAME, APP_VERSION, APP_AUTHOR, APP_DESCRIPTION

log = logging.getLogger(__name__)


class SettingsWindow:
    """Settings dialog - Light/Dark mode, Alpha slider"""

    def __init__(self, parent_root: tk.Tk, settings_data: dict, theme: Theme,
                 on_save_callback=None, main_root: tk.Tk = None, on_window_closed=None):
        try:
            log.debug("[Settings] Initializing SettingsWindow...")
            self.parent = parent_root  # Parent of SettingsWindow (for Toplevel)
            self.main_root = main_root or parent_root  # Main QuickNote window (for alpha/colors)
            self.settings = settings_data
            self.theme = theme
            self.on_save = on_save_callback or (lambda: None)
            self.on_window_closed = on_window_closed or (lambda: None)  # v1.5.2: callback when window closes

            # Create window
            log.debug("[Settings] Creating Toplevel window...")
            self.root = tk.Toplevel(parent_root)
            self.root.overrideredirect(False)
            self.root.title("Settings")
            self.root.geometry("400x350")
            self.root.config(bg=theme.c("bg"))
            self.root.resizable(False, False)

            # Make it stay on top (force topmost) — v1.7.0: smart side-by-side positioning
            self.root.attributes("-topmost", True)

            # v1.7.0: Position Settings window to the right of main window (side-by-side)
            log.debug("[Settings] Positioning window side-by-side to main window...")
            self.root.update_idletasks()
            main_x = parent_root.winfo_x()
            main_y = parent_root.winfo_y()
            main_w = parent_root.winfo_width()
            settings_w = 400
            settings_h = 350

            # Try to place on right side first
            x = main_x + main_w + 10
            y = main_y

            # Check if position goes off-screen (right edge), if so place on left side
            try:
                import ctypes
                gsm = ctypes.windll.user32.GetSystemMetrics
                screen_w = gsm(0)  # SM_CXSCREEN
                if x + settings_w > screen_w:
                    # Not enough space on right, try left side
                    x = main_x - settings_w - 10
            except Exception as e:
                log.warning(f"[Settings] Could not check screen bounds: {e}")

            self.root.geometry(f"{settings_w}x{settings_h}+{int(x)}+{int(y)}")
            log.debug(f"[Settings] Window positioned at ({int(x)}, {int(y)})")

            # Ensure Settings window stays on top and focused (v1.7.0: prevent hiding behind main window)
            self.root.lift()
            self.root.focus_force()
            log.debug("[Settings] Window lifted to front")

            # Bind window close event — v1.5.2: properly clean up board's reference
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            log.debug("[Settings] WM_DELETE_WINDOW protocol bound")

            # v1.6.0: Register as theme change listener for real-time updates
            self.theme.register_theme_change_listener(self._on_theme_changed)
            log.debug("[Settings] Registered as theme change listener")

            # Use Notebook for tabs
            log.debug("[Settings] Creating Notebook...")
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

            # Settings Tab
            settings_frame = tk.Frame(self.notebook, bg=theme.c("bg"))
            self.notebook.add(settings_frame, text="Settings")

            # About Tab
            about_frame = tk.Frame(self.notebook, bg=theme.c("bg"))
            self.notebook.add(about_frame, text="About")
            log.debug("[Settings] Tabs created")

            # Main frame for settings
            main_frame = tk.Frame(settings_frame, bg=theme.c("bg"))
            main_frame.pack(fill="both", expand=True, padx=16, pady=16)

            # v1.7.0: Removed Theme Section (Light/Dark toggle)
            # Single unified neutral theme is now used by default

            # === Opacity Section ===
            alpha_label = tk.Label(
            main_frame,
            text="Opacity",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 11, "bold"),
            )
            alpha_label.pack(anchor="w", pady=(16, 8))

            alpha_frame = tk.Frame(main_frame, bg=theme.c("bg"))
            alpha_frame.pack(fill="x", pady=8)

            # Opacity: 20% to 100% (0.2 to 1.0), default 100% (1.0)
            default_alpha = settings_data.get("alpha", 1.0)
            # Clamp to valid range
            default_alpha = max(0.2, min(1.0, default_alpha))
            self.alpha_var = tk.DoubleVar(value=default_alpha)

            self.alpha_slider = tk.Scale(
            alpha_frame,
            from_=0.2,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            variable=self.alpha_var,
            bg=theme.c("note_bg"),
            fg=theme.c("fg"),
            highlightthickness=0,
            command=self._on_alpha_change,
            )
            self.alpha_slider.pack(side="left", fill="x", expand=True)

            self.alpha_label_val = tk.Label(
            alpha_frame,
            text=f"{self.alpha_var.get():.0%}",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=FONT_UI,
            width=5,
            )
            self.alpha_label_val.pack(side="left", padx=8)

            # === Data Backup Section ===
            backup_label = tk.Label(
                main_frame,
                text="Data Backup & Restore",
                bg=theme.c("bg"),
                fg=theme.c("fg"),
                font=("Segoe UI", 11, "bold"),
            )
            backup_label.pack(anchor="w", pady=(16, 8))

            backup_button_frame = tk.Frame(main_frame, bg=theme.c("bg"))
            backup_button_frame.pack(fill="x", pady=8)

            self.btn_backup = tk.Button(
                backup_button_frame,
                text="Backup Data",
                bg="#007AFF",
                fg="#FFFFFF",
                font=("Segoe UI", 9),
                bd=0,
                relief="flat",
                command=self._on_backup,
            )
            self.btn_backup.pack(side="left", padx=4)

            self.btn_restore = tk.Button(
                backup_button_frame,
                text="Restore Data",
                bg="#FF9500",
                fg="#FFFFFF",
                font=("Segoe UI", 9),
                bd=0,
                relief="flat",
                command=self._on_restore,
            )
            self.btn_restore.pack(side="left", padx=4)

            # === Buttons (Settings Tab) ===
            button_frame = tk.Frame(main_frame, bg=theme.c("bg"))
            button_frame.pack(fill="x", pady=(16, 0))

            self.btn_close = tk.Button(
            button_frame,
            text="Close",
            bg=theme.c("accent"),
            fg="#FFFFFF",
            font=FONT_UI,
            bd=0,
            relief="flat",
            command=self._on_close,
            )
            self.btn_close.pack(side="right", padx=4)

            # === About Tab Content ===
            about_inner = tk.Frame(about_frame, bg=theme.c("bg"))
            about_inner.pack(fill="both", expand=True, padx=16, pady=16)

            # App name
            app_name_label = tk.Label(
            about_inner,
            text=APP_NAME,
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 16, "bold"),
            )
            app_name_label.pack(anchor="w", pady=(0, 4))

            # Version
            version_label = tk.Label(
            about_inner,
            text=f"Version {APP_VERSION}",
            bg=theme.c("bg"),
            fg=theme.c("fg_muted"),
            font=("Segoe UI", 10),
            )
            version_label.pack(anchor="w", pady=(0, 12))

            # Description
            desc_label = tk.Label(
            about_inner,
            text=APP_DESCRIPTION,
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 9),
            wraplength=350,
            justify="left",
            )
            desc_label.pack(anchor="w", pady=(0, 16))

            # Separator
            sep = tk.Frame(about_inner, bg=theme.c("border"), height=1)
            sep.pack(fill="x", pady=12)

            # Developer credit
            author_label = tk.Label(
            about_inner,
            text=f"Created by {APP_AUTHOR}",
            bg=theme.c("bg"),
            fg=theme.c("fg_muted"),
            font=("Segoe UI", 9),
            )
            author_label.pack(anchor="w", pady=(0, 4))

            credits_label = tk.Label(
                about_inner,
                text="Built with Python, tkinter, and SQLite3",
                bg=theme.c("bg"),
                fg=theme.c("fg_muted"),
                font=("Segoe UI", 8),
            )
            credits_label.pack(anchor="w")

            log.info("[Settings] SettingsWindow initialized successfully")
        except Exception as e:
            log.error(f"[Settings] Failed to initialize: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _on_alpha_change(self, value):
        """Apply opacity change to main window ONLY (Settings window stays opaque)"""
        try:
            alpha = float(value)
            alpha = max(0.2, min(1.0, alpha))
            # Update label display
            if hasattr(self, 'alpha_label_val') and self.alpha_label_val:
                self.alpha_label_val.config(text=f"{int(alpha * 100)}%")
            # Update settings (handle both dict and Settings object)
            if isinstance(self.settings, dict):
                self.settings["alpha"] = alpha
            elif hasattr(self.settings, 'data'):
                self.settings.data["alpha"] = alpha
            # Apply alpha ONLY to main window (not Settings window!)
            # Ensure main_root is the main QuickNote window, not Settings window
            if self.main_root and self.main_root != self.root and self.main_root.winfo_exists():
                try:
                    self.main_root.attributes("-alpha", alpha)
                    log.debug(f"[Settings] Applied alpha to main window: {alpha:.2f}")
                except Exception as e:
                    log.warning(f"[Settings] Could not apply alpha: {e}")
            # Ensure Settings window is always fully opaque
            if hasattr(self, 'root') and self.root:
                try:
                    self.root.attributes("-alpha", 1.0)
                except Exception:
                    pass
        except Exception as e:
            log.error(f"[Settings] Failed to apply alpha: {e}")

    def _on_theme_changed(self, theme):
        """Handle real-time theme changes — v1.6.0"""
        try:
            log.debug(f"[Settings] Theme changed to {theme.mode}, updating colors...")
            # Update theme reference
            self.theme = theme
            # Update window colors
            self.root.config(bg=theme.c("bg"))
            self.notebook.config(bg=theme.c("bg"))
            # Update all frames and widgets
            self._update_window_colors()
            log.debug("[Settings] Settings window colors updated")
        except Exception as e:
            log.error(f"[Settings] Failed to update theme: {e}")

    def _update_window_colors(self):
        """Update all widget colors to match current theme — v1.6.0"""
        try:
            # This is a simplified version - in production you might want to recursively update all children
            for widget in self.root.winfo_children():
                try:
                    if hasattr(widget, 'config'):
                        if hasattr(widget, 'cget') and 'bg' in widget.keys():
                            widget.config(bg=self.theme.c("bg"))
                        if hasattr(widget, 'cget') and 'fg' in widget.keys():
                            widget.config(fg=self.theme.c("fg"))
                except Exception as e:
                    log.debug(f"[Settings] Could not update widget: {e}")
        except Exception as e:
            log.error(f"[Settings] Failed to update widget colors: {e}")

    def _on_close(self):
        """Close settings window and save — v1.5.2: notify board to clear reference, v1.6.0: unregister listener"""
        try:
            self.theme.unregister_theme_change_listener(self._on_theme_changed)  # v1.6.0
        except Exception as e:
            log.error(f"[Settings] Failed to unregister theme listener: {e}")
        try:
            self.on_save()
        except Exception as e:
            log.error(f"[Settings] on_save callback failed: {e}")
        try:
            self.on_window_closed()  # v1.5.2: notify board that window is closing
        except Exception as e:
            log.error(f"[Settings] on_window_closed callback failed: {e}")
        try:
            self.root.destroy()
        except Exception as e:
            log.error(f"[Settings] window destroy failed: {e}")

    def _on_backup(self):
        """v2.4.0: Backup database to user-selected location"""
        try:
            from tkinter import filedialog, messagebox
            from ..core.database import backup_database

            # Open file save dialog
            file_path = filedialog.asksaveasfilename(
                title="Backup Database",
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("Backup files", "*.bak"), ("All files", "*.*")]
            )

            if file_path:
                # Perform backup
                if backup_database(file_path):
                    messagebox.showinfo("Success", f"Database backed up to:\n{file_path}")
                    log.info(f"[Settings] Database backed up to {file_path}")
                else:
                    messagebox.showerror("Error", "Failed to backup database")
                    log.error("[Settings] Backup failed")
        except Exception as e:
            log.error(f"[Settings] Backup error: {e}")
            try:
                from tkinter import messagebox
                messagebox.showerror("Error", f"Backup failed: {e}")
            except Exception:
                pass

    def _on_restore(self):
        """v2.4.0: Restore database from user-selected backup file"""
        try:
            from tkinter import filedialog, messagebox
            from ..core.database import restore_database

            # Open file open dialog
            file_path = filedialog.askopenfilename(
                title="Restore Database",
                filetypes=[("Database files", "*.db"), ("Backup files", "*.bak"), ("All files", "*.*")]
            )

            if file_path:
                # Confirm action
                result = messagebox.askyesno(
                    "Confirm Restore",
                    "This will replace your current data. Are you sure?"
                )
                if result:
                    # Perform restore
                    if restore_database(file_path):
                        messagebox.showinfo("Success", "Database restored successfully")
                        log.info(f"[Settings] Database restored from {file_path}")
                        # Trigger reload callback to update UI
                        if callable(self.on_save):
                            self.on_save()
                    else:
                        messagebox.showerror("Error", "Failed to restore database")
                        log.error("[Settings] Restore failed")
        except Exception as e:
            log.error(f"[Settings] Restore error: {e}")
            try:
                from tkinter import messagebox
                messagebox.showerror("Error", f"Restore failed: {e}")
            except Exception:
                pass


# Import FONT_UI to avoid circular import
from .theme import FONT_UI
