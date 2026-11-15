"""Centralized visual theme configuration for the PyLex Studio interface."""

import ttkbootstrap as ttkb

THEMES = {
    "dark": {
        "bootstrap_theme": "darkly",
        "window_bg": "#1B2028",
        "editor_bg": "#1E242D",
        "editor_fg": "#D8DEE8",
        "selection_bg": "#344354",
        "menu_bg": "#252D38",
        "menu_fg": "#D8DEE8",
        "accent": "#8FB7D8",
        "accent_hover": "#A5C7E2",
        "violet": "#B5A6D8",
        "run": "#8FB7D8",
        "run_hover": "#344354",
        "danger": "#E58B91",
        "danger_hover": "#C96F78",
        "success": "#83B9A6",
        "warning": "#D9B77C",
        "muted": "#9AA7B7",
        "surface": "#252D38",
        "elevated": "#303B49",
        "panel_bg": "#202832",
        "current_line": "#252F3A",
        "error_line": "#432D35",
        "bracket_bg": "#354657",
        "border": "#394655",
        "file_python": "#8FB7D8",
        "file_web": "#D9B77C",
        "file_markup": "#D99A83",
        "file_style": "#B5A6D8",
        "file_data": "#83B9A6",
        "file_shell": "#B5A6D8",
        "file_compiled": "#9AA7B7",
        "file_image": "#C99BB7",
        "file_audio": "#C99BB7",
        "file_video": "#C99BB7",
        "file_pdf": "#E58B91",
        "file_document": "#9AA7B7",
        "file_archive": "#D9B77C",
        "file_database": "#83B9B3",
        "file_font": "#B5A6D8",
        "file_text": "#B5C0CE",
        "file_binary": "#8C99A9",
        "file_unknown": "#8C99A9",
    },
    "light": {
        "bootstrap_theme": "minty-light",
        "window_bg": "#EAF0F8",
        "editor_bg": "#ffffff",
        "editor_fg": "#202938",
        "selection_bg": "#DCE8FF",
        "menu_bg": "#ffffff",
        "menu_fg": "#202938",
        "accent": "#286FE5",
        "accent_hover": "#1D5BC4",
        "violet": "#7656CF",
        "run": "#6847D8",
        "run_hover": "#5435BE",
        "danger": "#D84C62",
        "danger_hover": "#B93B50",
        "success": "#178A68",
        "warning": "#A96A12",
        "muted": "#65758D",
        "surface": "#F8FAFE",
        "elevated": "#E4ECF7",
        "panel_bg": "#EEF3FA",
        "current_line": "#F3F6FC",
        "error_line": "#FFE9ED",
        "bracket_bg": "#DCE8FF",
        "border": "#D6E0EE",
        "file_python": "#236fba",
        "file_web": "#9a6b00",
        "file_markup": "#bd573e",
        "file_style": "#7656CF",
        "file_data": "#267b60",
        "file_shell": "#7656CF",
        "file_compiled": "#52657d",
        "file_image": "#a34883",
        "file_audio": "#a34883",
        "file_video": "#a34883",
        "file_pdf": "#b43f38",
        "file_document": "#52657d",
        "file_archive": "#93611d",
        "file_database": "#167b78",
        "file_font": "#7656CF",
        "file_text": "#53657d",
        "file_binary": "#65758D",
        "file_unknown": "#65758D",
    },
}


def get_theme(theme):
    """Return the normalized theme definition without creating GUI widgets."""
    return THEMES["light" if theme == "light" else "dark"]


class ThemeManager:
    """Apply coordinated ttkbootstrap themes and PyLex-specific widget styles."""

    def __init__(self, root):
        self.root = root
        self.style = ttkb.Style(theme="vapor-dark")

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
        self.style.configure("TRadiobutton", font=ui_font)
        self.style.configure("TMenubutton", font=ui_font)
        self.style.configure(
            "TLabelframe.Label",
            font=(ui_font_family, ui_font_size, "bold"),
        )
        self.style.configure("TNotebook", tabmargins=(4, 5, 4, 0))
        self.style.configure("TSeparator", background=palette["border"])

        self.style.configure(
            "PyLex.Toolbar.TFrame",
            background=palette["surface"],
        )
        self.style.configure(
            "PyLex.Workspace.TFrame",
            background=palette["window_bg"],
        )
        self.style.configure(
            "PyLex.Brand.TLabel",
            background=palette["surface"],
            foreground=palette["editor_fg"],
            font=(ui_font_family, ui_font_size + 3, "bold"),
            padding=(0, 2),
        )
        self.style.configure(
            "PyLex.Status.TLabel",
            background=palette["surface"],
            foreground=palette["muted"],
            font=(ui_font_family, max(7, ui_font_size - 1)),
            padding=(4, 1),
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
            "PyLex.Menu.TMenubutton",
            font=(ui_font_family, ui_font_size + 1, "bold"),
            padding=(12, 7),
            borderwidth=0,
            background=palette["surface"],
            foreground=palette["editor_fg"],
        )
        self.style.configure(
            "PyLex.Menu.TButton",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(7, 3),
            borderwidth=0,
            background=palette["surface"],
            foreground=palette["editor_fg"],
            relief="flat",
            focusthickness=0,
            focuscolor=palette["surface"],
        )
        self.style.map(
            "PyLex.Menu.TButton",
            background=[
                ("active", palette["elevated"]),
                ("pressed", palette["surface"]),
            ],
            foreground=[
                ("active", palette["accent"]),
                ("pressed", palette["accent"]),
            ],
        )
        self.style.map(
            "PyLex.Menu.TMenubutton",
            background=[
                ("active", palette["elevated"]),
                ("pressed", palette["surface"]),
            ],
            foreground=[
                ("active", palette["accent"]),
                ("pressed", palette["accent"]),
            ],
        )
        self.style.configure(
            "PyLex.Activity.TFrame",
            background=palette["panel_bg"],
        )
        self.style.configure(
            "PyLex.Activity.TButton",
            font=(ui_font_family, max(7, ui_font_size - 2), "bold"),
            padding=(3, 7),
            borderwidth=0,
            background=palette["panel_bg"],
            foreground=palette["muted"],
            relief="flat",
            focusthickness=0,
            focuscolor=palette["panel_bg"],
        )
        self.style.map(
            "PyLex.Activity.TButton",
            background=[
                ("selected", palette["selection_bg"]),
                ("active", palette["elevated"]),
                ("pressed", palette["selection_bg"]),
            ],
            foreground=[
                ("selected", palette["accent"]),
                ("active", palette["editor_fg"]),
                ("pressed", palette["accent"]),
            ],
        )
        self.style.configure(
            "PyLex.IconAction.TButton",
            font=(ui_font_family, max(7, ui_font_size - 2)),
            padding=(5, 5),
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
            background=[
                ("disabled", palette["panel_bg"]),
                ("pressed", palette["accent_hover"]),
                ("active", palette["accent_hover"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("pressed", "#ffffff"),
                ("active", "#ffffff"),
            ],
        )
        self.style.configure(
            "PyLex.Run.TButton",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(14, 8),
            background=palette["surface"],
            foreground=palette["accent"],
            borderwidth=1,
            relief="solid",
            focusthickness=0,
            focuscolor=palette["surface"],
        )
        self.style.map(
            "PyLex.Run.TButton",
            background=[
                ("disabled", palette["panel_bg"]),
                ("pressed", palette["elevated"]),
                ("active", palette["elevated"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("!disabled", palette["accent"]),
            ],
        )
        self.style.configure(
            "PyLex.Stop.TButton",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(14, 8),
            background=palette["surface"],
            foreground=palette["danger"],
            borderwidth=1,
            relief="solid",
        )
        self.style.map(
            "PyLex.Stop.TButton",
            background=[
                ("disabled", palette["panel_bg"]),
                ("pressed", palette["error_line"]),
                ("active", palette["error_line"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("!disabled", palette["danger"]),
            ],
        )
        self.style.configure(
            "PyLex.Danger.TButton",
            font=ui_font,
            padding=(12, 7),
            background=palette["danger"],
            foreground="#ffffff",
            borderwidth=0,
            relief="flat",
        )
        self.style.map(
            "PyLex.Danger.TButton",
            background=[
                ("disabled", palette["panel_bg"]),
                ("pressed", palette["danger_hover"]),
                ("active", palette["danger_hover"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("pressed", "#ffffff"),
                ("active", "#ffffff"),
            ],
        )
        self.style.configure(
            "PyLex.Toolbar.TButton",
            font=(ui_font_family, ui_font_size, "bold"),
            padding=(8, 7),
            borderwidth=0,
            relief="flat",
            background=palette["surface"],
            foreground=palette["editor_fg"],
        )
        self.style.map(
            "PyLex.Toolbar.TButton",
            background=[
                ("pressed", palette["surface"]),
                ("active", palette["elevated"]),
            ],
            foreground=[
                ("pressed", palette["editor_fg"]),
                ("active", palette["accent"]),
            ],
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
            font=ui_font,
            background=palette["surface"],
            foreground=palette["editor_fg"],
            fieldbackground=palette["surface"],
        )
        self.style.configure(
            "Treeview.Heading",
            font=(ui_font_family, ui_font_size, "bold"),
        )
        self.style.map(
            "Treeview",
            background=[("selected", palette["accent"])],
            foreground=[("selected", "#ffffff")],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", palette["surface"])],
            foreground=[("selected", palette["accent"])],
        )
        self.style.configure(
            "TNotebook.Tab",
            padding=(12, 7),
            font=ui_font,
        )
        self.style.configure(
            "TPanedwindow",
            sashwidth=7,
            sashrelief="flat",
        )
        return palette
