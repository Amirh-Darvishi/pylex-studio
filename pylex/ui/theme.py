"""Centralized visual theme configuration for the PyLex Studio interface."""

import ttkbootstrap as ttkb


THEMES = {
    "dark": {
        "bootstrap_theme": "darkly",
        "window_bg": "#171b24",
        "editor_bg": "#1d232e",
        "editor_fg": "#e6eaf2",
        "selection_bg": "#344d73",
        "menu_bg": "#202735",
        "menu_fg": "#e6eaf2",
        "accent": "#4f8cff",
        "accent_hover": "#3978e8",
        "danger": "#d95763",
        "muted": "#9aa7ba",
        "surface": "#202735",
    },
    "light": {
        "bootstrap_theme": "flatly",
        "window_bg": "#f3f6fb",
        "editor_bg": "#ffffff",
        "editor_fg": "#202938",
        "selection_bg": "#cfe0ff",
        "menu_bg": "#ffffff",
        "menu_fg": "#202938",
        "accent": "#2868c7",
        "accent_hover": "#1e55a8",
        "danger": "#c94350",
        "muted": "#68778d",
        "surface": "#ffffff",
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

    def apply(self, dark=True):
        """Apply a complete theme and return its palette for classic Tk widgets."""
        theme_name = "dark" if dark else "light"
        palette = get_theme(theme_name)
        self.style.theme_use(palette["bootstrap_theme"])

        self.style.configure(
            "PyLex.Toolbar.TFrame",
            background=palette["surface"],
        )
        self.style.configure(
            "PyLex.Brand.TLabel",
            background=palette["surface"],
            foreground=palette["editor_fg"],
            font=("Segoe UI", 12, "bold"),
            padding=(0, 2),
        )
        self.style.configure(
            "PyLex.Group.TLabel",
            background=palette["surface"],
            foreground=palette["muted"],
            font=("Segoe UI", 7, "bold"),
        )
        self.style.configure(
            "PyLex.Section.TLabel",
            font=("Segoe UI", 9, "bold"),
            padding=(2, 5),
        )
        self.style.configure(
            "PyLex.Toolbar.TButton",
            font=("Segoe UI", 9),
            padding=(10, 6),
            borderwidth=0,
        )
        self.style.configure(
            "PyLex.Primary.TButton",
            font=("Segoe UI", 9, "bold"),
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
            "PyLex.Status.TLabel",
            font=("Segoe UI", 8),
            padding=(10, 5),
        )
        self.style.configure(
            "Treeview",
            rowheight=25,
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
