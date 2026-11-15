"""Centralized visual theme configuration for the PyLex Studio interface."""

import ttkbootstrap as ttkb


THEMES = {
    "dark": {
        "bootstrap_theme": "darkly",
        "window_bg": "#111827",
        "editor_bg": "#111827",
        "editor_fg": "#e6edf7",
        "selection_bg": "#293b5b",
        "menu_bg": "#1b2433",
        "menu_fg": "#e6edf7",
        "accent": "#4f8cff",
        "accent_hover": "#3978e8",
        "violet": "#a78bfa",
        "danger": "#ef6b73",
        "success": "#4cc38a",
        "warning": "#e6b45a",
        "muted": "#91a0b7",
        "surface": "#1b2433",
        "panel_bg": "#161f2d",
        "current_line": "#182438",
        "error_line": "#48252e",
        "bracket_bg": "#344b70",
        "border": "#2b3648",
        "file_python": "#62b0ff",
        "file_web": "#e6bd68",
        "file_markup": "#e88c72",
        "file_style": "#b59aff",
        "file_data": "#71c7a5",
    },
    "light": {
        "bootstrap_theme": "flatly",
        "window_bg": "#f3f6fb",
        "editor_bg": "#ffffff",
        "editor_fg": "#202938",
        "selection_bg": "#d7e5ff",
        "menu_bg": "#ffffff",
        "menu_fg": "#202938",
        "accent": "#2868c7",
        "accent_hover": "#1e55a8",
        "violet": "#7655c8",
        "danger": "#c94350",
        "success": "#21845a",
        "warning": "#a66a12",
        "muted": "#68778d",
        "surface": "#ffffff",
        "panel_bg": "#edf2f9",
        "current_line": "#f1f5fc",
        "error_line": "#ffe8e8",
        "bracket_bg": "#d7e5ff",
        "border": "#d9e1ed",
        "file_python": "#236fba",
        "file_web": "#9a6b00",
        "file_markup": "#bd573e",
        "file_style": "#7655c8",
        "file_data": "#267b60",
    },
}


def get_theme(theme):
    """Return the normalized theme definition without creating GUI widgets."""
    return THEMES["light" if theme == "light" else "dark"]


class ThemeManager:
    """Apply coordinated ttkbootstrap themes and PyLex-specific widget styles."""

    def __init__(self, root):
        self.root = root
        self.style = ttkb.Style(theme="darkly")

    def apply(self, dark=True, ui_font_family="Segoe UI", ui_font_size=9):
        """Apply a complete theme and return its palette for classic Tk widgets."""
        theme_name = "dark" if dark else "light"
        palette = get_theme(theme_name)
        self.style.theme_use(palette["bootstrap_theme"])
        ui_font = (ui_font_family, ui_font_size)
        self.style.configure(".", font=ui_font)
        self.style.configure("TLabel", font=ui_font)
        self.style.configure("TButton", font=ui_font)
        self.style.configure("TEntry", font=ui_font)
        self.style.configure("TCombobox", font=ui_font)
        self.style.configure("TCheckbutton", font=ui_font)

        self.style.configure(
            "PyLex.Toolbar.TFrame",
            background=palette["surface"],
        )
        self.style.configure(
            "PyLex.Brand.TLabel",
            background=palette["surface"],
            foreground=palette["editor_fg"],
            font=(ui_font_family, ui_font_size + 3, "bold"),
            padding=(0, 2),
        )
        self.style.configure(
            "PyLex.Group.TLabel",
            background=palette["surface"],
            foreground=palette["muted"],
            font=(ui_font_family, max(7, ui_font_size - 2), "bold"),
        )
        self.style.configure(
            "PyLex.Section.TLabel",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(2, 5),
        )
        self.style.configure(
            "PyLex.Toolbar.TButton",
            font=ui_font,
            padding=(10, 6),
            borderwidth=0,
        )
        self.style.configure(
            "PyLex.Primary.TButton",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(12, 6),
            background=palette["accent"],
            foreground="#ffffff",
            borderwidth=0,
        )
        self.style.map(
            "PyLex.Primary.TButton",
            background=[("active", palette["accent_hover"])],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure(
            "PyLex.Danger.TButton",
            font=("Segoe UI", 9),
            padding=(10, 6),
            background=palette["danger"],
            foreground="#ffffff",
            borderwidth=0,
        )
        self.style.configure(
            "PyLex.Muted.TLabel",
            foreground=palette["muted"],
            font=(ui_font_family, max(8, ui_font_size - 1)),
        )
        self.style.configure(
            "PyLex.Field.TLabel",
            font=(ui_font_family, ui_font_size, "bold"),
        )
        self.style.configure(
            "PyLex.DialogTitle.TLabel",
            font=(ui_font_family, ui_font_size + 6, "bold"),
        )
        self.style.configure(
            "PyLex.AboutTitle.TLabel",
            font=(ui_font_family, ui_font_size + 9, "bold"),
            foreground=palette["accent"],
        )
        self.style.configure(
            "PyLex.Status.TLabel",
            font=(ui_font_family, max(8, ui_font_size - 1)),
            padding=(10, 5),
        )
        self.style.configure(
            "Treeview",
            rowheight=max(25, ui_font_size * 3),
            font=("Segoe UI", 9),
            background=palette["surface"],
            foreground=palette["editor_fg"],
            fieldbackground=palette["surface"],
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
        )
        self.style.configure(
            "TNotebook.Tab",
            padding=(12, 7),
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "TPanedwindow",
            sashwidth=5,
        )
        return palette
