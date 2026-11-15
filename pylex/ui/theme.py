"""Centralized visual theme configuration for the PyLex Studio interface."""

import ttkbootstrap as ttkb


THEMES = {
    "dark": {
        "bootstrap_theme": "vapor-dark",
        "window_bg": "#0B1220",
        "editor_bg": "#0B1220",
        "editor_fg": "#e6edf7",
        "selection_bg": "#263A5C",
        "menu_bg": "#172338",
        "menu_fg": "#e6edf7",
        "accent": "#62A5FF",
        "accent_hover": "#3D89F5",
        "violet": "#B39BFF",
        "danger": "#F07187",
        "danger_hover": "#D95770",
        "success": "#38D9A9",
        "warning": "#F2C66D",
        "muted": "#9AAAC2",
        "surface": "#172338",
        "elevated": "#202E46",
        "panel_bg": "#111B2E",
        "current_line": "#111D32",
        "error_line": "#48252e",
        "bracket_bg": "#314A72",
        "border": "#293A55",
        "file_python": "#62b0ff",
        "file_web": "#e6bd68",
        "file_markup": "#e88c72",
        "file_style": "#b59aff",
        "file_data": "#71c7a5",
        "file_shell": "#c7a6ff",
        "file_compiled": "#8fa4bd",
        "file_image": "#e58bbd",
        "file_audio": "#e58bbd",
        "file_video": "#e58bbd",
        "file_pdf": "#ef8d83",
        "file_document": "#8fa4bd",
        "file_archive": "#d5a56c",
        "file_database": "#6fc6c2",
        "file_font": "#c7a6ff",
        "file_text": "#aebbd0",
        "file_binary": "#8794a8",
        "file_unknown": "#8794a8",
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
        self.style.map(
            "PyLex.Menu.TMenubutton",
            background=[
                ("active", palette["selection_bg"]),
                ("pressed", palette["selection_bg"]),
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
            font=(ui_font_family, ui_font_size + 1, "bold"),
            padding=(16, 8),
            background=palette["accent"],
            foreground="#ffffff",
            borderwidth=0,
            relief="flat",
        )
        self.style.map(
            "PyLex.Run.TButton",
            background=[
                ("disabled", palette["panel_bg"]),
                ("pressed", palette["accent_hover"]),
                ("active", palette["accent_hover"]),
            ],
            foreground=[("disabled", palette["muted"]), ("!disabled", "#ffffff")],
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
            foreground=[("disabled", palette["muted"]), ("!disabled", palette["danger"])],
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
            background=[("active", palette["selection_bg"]), ("pressed", palette["selection_bg"])],
            foreground=[("active", palette["accent"]), ("pressed", palette["accent"])],
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
