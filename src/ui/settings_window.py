"""Settings Window — Theme, Alpha, Hotkey settings, About"""

import tkinter as tk
from tkinter import ttk
from .theme import Theme
from ..core.constants import APP_NAME, APP_VERSION, APP_AUTHOR, APP_DESCRIPTION


class SettingsWindow:
    """หน้าต่างตั้งค่า — Light/Dark mode, Alpha slider"""

    def __init__(self, parent_root: tk.Tk, settings_data: dict, theme: Theme,
                 on_save_callback=None):
        self.parent = parent_root
        self.settings = settings_data
        self.theme = theme
        self.on_save = on_save_callback or (lambda: None)

        # Create window
        self.root = tk.Toplevel(parent_root)
        self.root.overrideredirect(False)
        self.root.title("Settings")
        self.root.geometry("400x350")
        self.root.config(bg=theme.c("bg"))
        self.root.resizable(False, False)

        # Make it stay on top
        self.root.attributes("-topmost", True)

        # Center on parent
        self.root.update_idletasks()
        x = parent_root.winfo_x() + (parent_root.winfo_width() - 400) // 2
        y = parent_root.winfo_y() + (parent_root.winfo_height() - 350) // 2
        self.root.geometry(f"+{x}+{y}")

        # Use Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # Settings Tab
        settings_frame = tk.Frame(self.notebook, bg=theme.c("bg"))
        self.notebook.add(settings_frame, text="Settings")

        # About Tab
        about_frame = tk.Frame(self.notebook, bg=theme.c("bg"))
        self.notebook.add(about_frame, text="About")

        # Main frame for settings
        main_frame = tk.Frame(settings_frame, bg=theme.c("bg"))
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # === Theme Section ===
        theme_label = tk.Label(
            main_frame,
            text="Appearance",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            font=("Segoe UI", 11, "bold"),
        )
        theme_label.pack(anchor="w", pady=(0, 8))

        # Radio buttons
        self.theme_var = tk.StringVar(value=theme.mode)
        rb_light = tk.Radiobutton(
            main_frame,
            text="Light",
            variable=self.theme_var,
            value="light",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            selectcolor=theme.c("bg"),
            activebackground=theme.c("bg_hover"),
            command=self._on_theme_change,
        )
        rb_light.pack(anchor="w", pady=2)

        rb_dark = tk.Radiobutton(
            main_frame,
            text="Dark",
            variable=self.theme_var,
            value="dark",
            bg=theme.c("bg"),
            fg=theme.c("fg"),
            selectcolor=theme.c("bg"),
            activebackground=theme.c("bg_hover"),
            command=self._on_theme_change,
        )
        rb_dark.pack(anchor="w", pady=2)

        # === Alpha Section ===
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

        self.alpha_var = tk.DoubleVar(value=settings_data.get("alpha", 1.0))
        self.alpha_slider = tk.Scale(
            alpha_frame,
            from_=0.3,
            to=1.0,
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

    def _on_theme_change(self):
        """เมื่อเลือก theme"""
        new_theme = self.theme_var.get()
        self.settings["theme"] = new_theme
        # TODO: ส่งให้ board.py ทำการ apply_theme()

    def _on_alpha_change(self, value):
        """เมื่อปรับ alpha slider"""
        alpha = float(value)
        self.alpha_var.set(alpha)
        self.alpha_label_val.config(text=f"{alpha:.0%}")
        self.settings["alpha"] = alpha
        # TODO: ส่งให้ parent_root ตั้ง -alpha

    def _on_close(self):
        """ปิดหน้าต่างและเซฟค่าตั้ง"""
        self.on_save()
        self.root.destroy()


# Import FONT_UI ที่ท้ายเพื่อหลีกเลี่ยง circular import
from .theme import FONT_UI
