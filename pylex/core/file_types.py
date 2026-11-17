"""File type detection and safe text-file loading for the workspace."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileType:
    """Describe a workspace file without assuming it is Python source."""

    kind: str
    description: str
    icon: str
    mime_type: str | None
    is_text: bool


_ICON_GROUPS = {
    "python": ("🐍", "Python source"),
    "web": ("🌐", "Web source"),
    "markup": ("📑", "Markup document"),
    "style": ("🎨", "Stylesheet"),
    "data": ("🧾", "Structured data"),
    "config": ("⚙", "Configuration"),
    "shell": ("⌨", "Shell script"),
    "compiled": ("⚙", "Compiled or native file"),
    "image": ("🖼", "Image"),
    "audio": ("♫", "Audio"),
    "video": ("▶", "Video"),
    "pdf": ("📕", "PDF document"),
    "document": ("📘", "Office document"),
    "archive": ("📦", "Archive"),
    "database": ("🗄", "Database"),
    "font": ("🔤", "Font"),
    "text": ("📄", "Text file"),
    "binary": ("📦", "Binary file"),
    "unknown": ("📄", "Unknown file type"),
}

_EXTENSION_GROUPS = {
    "python": {".py", ".pyw", ".pyi"},
    "web": {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte"},
    "markup": {".html", ".htm", ".xml", ".xhtml", ".svg", ".md", ".rst", ".ipynb"},
    "style": {".css", ".scss", ".sass", ".less"},
    "data": {
        ".json",
        ".jsonc",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".csv",
        ".tsv",
    },
    "config": {
        ".conf",
        ".properties",
        ".env",
        ".editorconfig",
        ".gitignore",
        ".gitattributes",
    },
    "shell": {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"},
    "compiled": {
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".cxx",
        ".java",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
    },
    "binary": {
        ".class",
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".bin",
        ".o",
        ".obj",
        ".a",
        ".lib",
        ".dylib",
    },
    "image": {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".webp",
        ".ico",
        ".tif",
        ".tiff",
        ".heic",
        ".avif",
    },
    "audio": {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"},
    "pdf": {".pdf"},
    "document": {
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".ods",
    },
    "archive": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".whl"},
    "database": {".db", ".sqlite", ".sqlite3", ".mdb"},
    "font": {".ttf", ".otf", ".woff", ".woff2"},
    "text": {".txt", ".log", ".rst", ".tex", ".adoc", ".lock", ".make", ".mk"},
}

_SPECIAL_NAMES = {
    "dockerfile": ("config", "⚙", "Container configuration", True),
    "makefile": ("config", "⚙", "Build configuration", True),
    "procfile": ("config", "⚙", "Process configuration", True),
    ".gitignore": ("config", "⚙", "Git configuration", True),
    ".dockerignore": ("config", "⚙", "Container configuration", True),
    ".editorconfig": ("config", "⚙", "Editor configuration", True),
    ".npmrc": ("config", "⚙", "Package manager configuration", True),
    ".prettierrc": ("config", "⚙", "Formatter configuration", True),
    ".env": ("config", "⚙", "Environment configuration", True),
    "license": ("text", "📄", "License text", True),
    "readme": ("markup", "📑", "Project documentation", True),
}


def file_type_for(path) -> FileType:
    """Classify a file using special names, extensions, MIME, and content."""
    path = Path(path)
    name = path.name.lower()
    suffix = path.suffix.lower()
    mime_type, _encoding = mimetypes.guess_type(str(path))

    special = _SPECIAL_NAMES.get(name)
    if special is None and name.startswith("readme"):
        special = _SPECIAL_NAMES["readme"]
    if special:
        kind, icon, description, is_text = special
        return FileType(kind, description, icon, mime_type, is_text)

    for kind, extensions in _EXTENSION_GROUPS.items():
        if suffix in extensions:
            icon, description = _ICON_GROUPS[kind]
            return FileType(
                kind,
                description,
                icon,
                mime_type,
                kind
                in {
                    "python",
                    "web",
                    "markup",
                    "style",
                    "data",
                    "config",
                    "shell",
                    "compiled",
                    "text",
                },
            )

    if mime_type:
        if mime_type.startswith("text/") or mime_type in {
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-sh",
            "application/x-python",
        }:
            return FileType("text", "Text file", "📄", mime_type, True)
        if mime_type.startswith("image/"):
            return FileType("image", "Image", "🖼", mime_type, False)
        if mime_type.startswith("audio/"):
            return FileType("audio", "Audio", "♫", mime_type, False)
        if mime_type.startswith("video/"):
            return FileType("video", "Video", "▶", mime_type, False)
        if mime_type == "application/pdf":
            return FileType("pdf", "PDF document", "📕", mime_type, False)

    try:
        sample = path.read_bytes()[:8192]
    except OSError:
        sample = b""
    if sample and b"\x00" not in sample:
        try:
            sample.decode("utf-8")
            return FileType("text", "UTF-8 text file", "📄", mime_type, True)
        except UnicodeDecodeError:
            pass
    return FileType("unknown", "Unknown or binary file", "📄", mime_type, False)


def read_text_file_details(path) -> tuple[str, str, str]:
    """Read text and return its detected encoding and first newline convention."""
    path = Path(path)
    info = file_type_for(path)
    if not info.is_text:
        raise UnicodeError(f"{path.name} is not recognized as a text file.")
    data = path.read_bytes()
    if b"\x00" in data:
        raise UnicodeError(f"{path.name} contains binary data.")

    if data.startswith(b"\xef\xbb\xbf"):
        candidates = ("utf-8-sig",)
    else:
        candidates = ("utf-8", "cp1252")
    for encoding in candidates:
        try:
            content = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeError(f"{path.name} could not be decoded as text.")

    crlf = content.find("\r\n")
    lf = content.find("\n")
    cr = content.find("\r")
    endings = [(index, value) for index, value in ((crlf, "\r\n"), (lf, "\n"), (cr, "\r")) if index >= 0]
    newline = min(endings, key=lambda item: item[0])[1] if endings else "\n"
    return content, encoding, newline


def read_text_file(path) -> str:
    """Read a text file with common Unicode encodings, rejecting binary data."""
    return read_text_file_details(path)[0]
