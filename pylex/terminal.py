"""Integrated shell sessions with asynchronous, non-blocking output capture."""
from __future__ import annotations
import os
from pathlib import Path, PureWindowsPath
import queue
import shutil
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
import time

from .ui.context_menu import ContextMenu

def available_shells():
    """Return supported shells available on the current operating system."""
    if os.name == "nt":
        shells = [("PowerShell", "powershell"), ("Command Prompt", "cmd")]
        git_bash = shutil.which("bash")
        if not git_bash:
            roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
            for root in roots:
                candidate = Path(root) / "Git" / "bin" / "bash.exe"
                if candidate.is_file():
                    git_bash = str(candidate)
                    break
        if git_bash:
            shells.append(("Git Bash", "git-bash"))
        return shells
    shells = []
    if shutil.which("bash"):
        shells.append(("Bash", "bash"))
    if shutil.which("zsh"):
        shells.append(("Zsh", "zsh"))
    if shutil.which("sh"):
        shells.append(("POSIX Shell", "sh"))
    return shells or [("System Shell", "sh")]

def shell_command(shell):
    """Build a shell launch command without passing user input through a shell."""
    if shell == "powershell":
        return [shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe",
                "-NoLogo", "-NoProfile", "-NoExit"]
    if shell == "cmd":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/Q", "/K"]
    if shell == "git-bash":
        return [shutil.which("bash") or "bash.exe", "--noprofile", "--norc", "-i"]
    if shell in {"bash", "zsh", "sh"}:
        executable = shutil.which(shell) or shell
        return [executable, "--noprofile", "--norc", "-i"] if shell in {"bash", "zsh"} else [executable]
    raise ValueError("Unsupported terminal shell: " + str(shell))

def terminal_environment(base=None, python_executable=None):
    """Prepare a shell environment that prefers the selected project interpreter."""
    env = dict(os.environ if base is None else base)
    env.setdefault("PYTHONUNBUFFERED", "1")
    if python_executable:
        raw_executable = str(python_executable)
        if "\\" in raw_executable or (len(raw_executable) > 1 and raw_executable[1] == ":"):
            executable = PureWindowsPath(raw_executable)
        else:
            executable = Path(raw_executable).expanduser()
        scripts = executable.parent
        env["PATH"] = str(scripts) + os.pathsep + env.get("PATH", "")
        if scripts.name.lower() in {"scripts", "bin"}:
            env["VIRTUAL_ENV"] = str(scripts.parent)
            env.pop("PYTHONHOME", None)
    return env

def terminate_process_tree(process):
    """Terminate a shell and its descendants, including child commands."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False, timeout=5)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            process.kill()
        except OSError:
            pass

class TerminalProcess:
    """Thread-safe interactive shell process; all UI access stays on the Tk thread."""
    def __init__(self, process, shell, cwd):
        self.process = process
        self.shell = shell
        self.cwd = Path(cwd).resolve()
        self.events = queue.Queue()
        self.done = threading.Event()
        self.exit_code = None
        self.started_at = time.monotonic()
        self._write_lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._waiter = threading.Thread(target=self._wait_for_exit, daemon=True)
        self._reader.start()
        self._waiter.start()

    @classmethod
    def start(cls, shell, cwd=None, env=None):
        """Start a persistent shell in the requested directory and environment."""
        directory = Path(cwd or Path.cwd()).expanduser().resolve()
        if not directory.is_dir():
            raise NotADirectoryError("Terminal working directory does not exist: " + str(directory))
        options = ({"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
                   if os.name == "nt" else {"start_new_session": True})
        process = subprocess.Popen(
            shell_command(shell), cwd=str(directory), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, **options)
        return cls(process, shell, directory)

    @property
    def running(self):
        return not self.done.is_set() and self.process.poll() is None

    def _read_output(self):
        pending = []
        try:
            while True:
                char = self.process.stdout.read(1)
                if char == "":
                    break
                pending.append(char)
                if char == "\n" or len(pending) >= 256:
                    self.events.put("".join(pending))
                    pending.clear()
        except (OSError, ValueError):
            pass
        if pending:
            self.events.put("".join(pending))

    def _wait_for_exit(self):
        try:
            self.exit_code = self.process.wait()
        finally:
            self._reader.join(timeout=2)
            self.done.set()

    def send(self, command):
        """Send one line to the existing shell, preserving its working directory."""
        if not self.running:
            raise RuntimeError("This terminal session is no longer running.")
        if "\x00" in command:
            raise ValueError("Terminal input cannot contain a NUL character.")
        with self._write_lock:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

    def interrupt(self):
        """Send Ctrl+C to the shell process group without closing the session."""
        if not self.running:
            return False
        try:
            if os.name == "nt":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(self.process.pid, signal.SIGINT)
            return True
        except (OSError, ValueError):
            return False

    def stop(self):
        """Force-stop the shell and every child process."""
        if not self.running:
            return False
        terminate_process_tree(self.process)
        return True

    def read_available(self):
        chunks = []
        while True:
            try:
                chunks.append(self.events.get_nowait())
            except queue.Empty:
                return chunks

class TerminalPanel(ttk.Frame):
    """Dockable terminal panel with multiple independent shell sessions."""
    def __init__(self, master, context_provider, default_shell="", on_shell_change=None):
        super().__init__(master)
        self.context_provider = context_provider
        self.on_shell_change = on_shell_change
        self.shells = available_shells()
        shell_ids = [item[1] for item in self.shells]
        selected = default_shell if default_shell in shell_ids else (
            "powershell" if os.name == "nt" else shell_ids[0])
        self.shell_var = tk.StringVar(value=selected)
        self.sessions = {}
        self.views = {}
        self._counter = 0
        self._poll_id = None
        toolbar = ttk.Frame(self, padding=(5, 4))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Shell").pack(side="left", padx=(0, 4))
        self.shell_box = ttk.Combobox(toolbar, textvariable=self.shell_var,
                                      values=shell_ids, state="readonly", width=14)
        self.shell_box.pack(side="left", padx=(0, 6))
        self.shell_box.bind("<<ComboboxSelected>>", self._shell_changed)
        ttk.Button(toolbar, text="New Terminal", command=self.create_session).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Interrupt", command=self.interrupt_current).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Kill", command=self.stop_current).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Clear", command=self.clear_current).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Close Session", command=self.close_current).pack(side="left", padx=2)
        self.status = ttk.Label(toolbar, text="No terminal session")
        self.status.pack(side="right", padx=6)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        self._poll_id = self.after(80, self._poll)

    @property
    def session_count(self):
        return len(self.sessions)

    def _shell_changed(self, _event=None):
        if self.on_shell_change:
            self.on_shell_change(self.shell_var.get())

    def create_session(self, shell=None):
        shell = shell or self.shell_var.get()
        try:
            cwd, env, python_executable = self.context_provider()
            env = terminal_environment(env, python_executable)
            process = TerminalProcess.start(shell, cwd=cwd, env=env)
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.configure(text="Could not start terminal: " + str(exc))
            return None
        self._counter += 1
        frame = ttk.Frame(self.notebook)
        output_frame = ttk.Frame(frame)
        output_frame.pack(fill="both", expand=True)
        output = tk.Text(output_frame, wrap="none", height=8, font=("Consolas", 10),
                         undo=False, state="disabled")
        output.tag_configure("system", foreground="#4b83c3")
        output.tag_configure("error", foreground="#d9534f")
        output.bind("<Button-3>", lambda event, widget=output: self._show_output_context_menu(widget, event), add="+")
        output.grid(row=0, column=0, columnspan=2, sticky="nsew")
        output.bind(
            "<Shift-MouseWheel>",
            lambda event: (output.xview_scroll(-int(event.delta / 120) * 3, "units"), "break"),
            add="+",
        )
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        input_row = ttk.Frame(frame, padding=(4, 4))
        input_row.pack(fill="x")
        ttk.Label(input_row, text="›").pack(side="left", padx=(2, 6))
        entry = ttk.Entry(input_row)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _event, item=frame: self._send(item))
        entry.bind("<Button-3>", lambda event, widget=entry: self._show_entry_context_menu(widget, event), add="+")
        entry.bind("<Up>", lambda _event, item=frame: self._history_move(item, -1))
        entry.bind("<Down>", lambda _event, item=frame: self._history_move(item, 1))
        entry.bind("<Control-c>", lambda _event: self.interrupt_current())
        self.sessions[frame] = process
        self.views[frame] = {
            "output": output, "entry": entry, "shell": shell,
            "history": [], "history_index": 0, "history_draft": "",
        }
        label = dict((key, name) for name, key in self.shells).get(shell, shell)
        self.notebook.add(frame, text=f"{label} {self._counter}")
        self.notebook.select(frame)
        output.configure(state="normal")
        output.insert("end", f"[{label}] {cwd}\n", "system")
        output.configure(state="disabled")
        entry.focus_set()
        self.status.configure(text=f"Running — {cwd}")
        return process

    def _context_menu(self):
        root = self.winfo_toplevel()
        preferences = getattr(root, "preferences", {})
        font_family = root._resolved_ui_font() if hasattr(root, "_resolved_ui_font") else "Segoe UI"
        return ContextMenu(
            self, palette=getattr(root, "theme_palette", {}),
            font_family=font_family, font_size=preferences.get("ui_font_size", 9),
        )

    def _show_output_context_menu(self, widget, event):
        menu = self._context_menu()
        try:
            selected = bool(widget.tag_ranges("sel"))
        except tk.TclError:
            selected = False
        menu.add_command(
            label="Copy Selection",
            command=lambda: widget.event_generate("<<Copy>>"),
            state="normal" if selected else "disabled",
        )
        menu.add_command(
            label="Select All",
            command=lambda: widget.tag_add("sel", "1.0", "end-1c"),
        )
        menu.add_separator()
        menu.add_command(label="Clear Terminal Output", command=lambda: self._clear_output(widget))
        menu.add_command(label="Interrupt Current Command", command=self.interrupt_current)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _clear_output(self, widget):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.configure(state='disabled')

    def _show_entry_context_menu(self, widget, event):
        menu = self._context_menu()
        try:
            selected = bool(widget.selection_present())
        except tk.TclError:
            selected = False
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"),
                         state="normal" if selected else "disabled")
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"),
                         state="normal" if selected else "disabled")
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Select All", command=lambda: widget.select_range(0, "end"))
        menu.add_command(label="Clear Input", command=lambda: widget.delete(0, "end"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _current_frame(self):
        selected = self.notebook.select()
        return self.nametowidget(selected) if selected else None

    def _tab_changed(self, _event=None):
        frame = self._current_frame()
        if frame in self.sessions:
            session = self.sessions[frame]
            self.status.configure(text=("Running — " if session.running else "Exited — ")
                                  + str(session.cwd))

    def _send(self, frame):
        session = self.sessions.get(frame)
        view = self.views.get(frame)
        if session is None or view is None:
            return
        command = view["entry"].get()
        if not command.strip():
            return
        self._append(frame, f"> {command}\n")
        if not view["history"] or view["history"][-1] != command:
            view["history"].append(command)
        view["history_index"] = len(view["history"])
        view["history_draft"] = ""
        view["entry"].delete(0, "end")
        try:
            session.send(command)
        except (OSError, RuntimeError, ValueError) as exc:
            self._append(frame, f"{type(exc).__name__}: {exc}\n", "error")
            self.status.configure(text="Input failed.")

    def _history_move(self, frame, direction):
        """Navigate command history while preserving any unsubmitted draft."""
        view = self.views.get(frame)
        if not view or not view["history"]:
            return "break"
        entry = view["entry"]
        history = view["history"]
        index = view["history_index"]
        if index == len(history):
            view["history_draft"] = entry.get()
        index = max(0, min(len(history), index + direction))
        view["history_index"] = index
        value = history[index] if index < len(history) else view["history_draft"]
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.icursor("end")
        return "break"

    def _append(self, frame, value, tag=None):
        view = self.views.get(frame)
        if not view:
            return
        output = view["output"]
        output.configure(state="normal")
        output.insert("end", value, tag or ())
        output.see("end")
        output.configure(state="disabled")

    def _poll(self):
        for frame, session in list(self.sessions.items()):
            for chunk in session.read_available():
                self._append(frame, chunk)
            if session.done and not getattr(session, "_reported_exit", False):
                session._reported_exit = True
                self._append(frame, f"\n[Shell exited with code {session.exit_code}]\n", "system")
                if self._current_frame() == frame:
                    self.status.configure(text=f"Shell exited — code {session.exit_code}")
        try:
            self._poll_id = self.after(80, self._poll)
        except tk.TclError:
            self._poll_id = None

    def interrupt_current(self):
        session = self.sessions.get(self._current_frame())
        if session and session.interrupt():
            self.status.configure(text="Interrupt signal sent (Ctrl+C).")

    def stop_current(self):
        session = self.sessions.get(self._current_frame())
        if session and session.stop():
            self.status.configure(text="Stopping terminal process tree...")

    def clear_current(self):
        frame = self._current_frame()
        if frame in self.views:
            output = self.views[frame]["output"]
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.configure(state="disabled")

    def close_current(self):
        frame = self._current_frame()
        if frame not in self.sessions:
            return
        session = self.sessions.pop(frame)
        session.stop()
        try:
            session.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            terminate_process_tree(session.process)
        self.views.pop(frame, None)
        self.notebook.forget(frame)
        frame.destroy()
        self.status.configure(text="Terminal session closed.")

    def set_theme(self, dark, palette=None):
        palette = palette or {}
        bg = palette.get("editor_bg", "#111827" if dark else "#ffffff")
        fg = palette.get("editor_fg", "#e6edf7" if dark else "#202938")
        selection = palette.get("selection_bg", "#293b5b" if dark else "#d7e5ff")
        for view in self.views.values():
            view["output"].configure(
                bg=bg, fg=fg, insertbackground=fg,
                selectbackground=selection, selectforeground=fg,
            )

    def close_all(self):
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        for session in list(self.sessions.values()):
            session.stop()
        for session in list(self.sessions.values()):
            try:
                session.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                terminate_process_tree(session.process)
        self.sessions.clear()
        self.views.clear()
