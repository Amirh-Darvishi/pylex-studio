"""Process-tree ownership helpers for execution, terminal and debugger sessions."""

import os


def attach_process_job(process):
    """Attach a Windows child to a kill-on-close Job Object when possible.

    POSIX launches already use a dedicated process group. A Windows Job Object
    keeps descendants associated with the session after its leader exits.
    """
    if os.name != "nt":
        return False

    job = None
    kernel32 = None
    try:
        import ctypes
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return False

        limits = ExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = 0x2000
        configured = kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        assigned = configured and kernel32.AssignProcessToJobObject(
            job, wintypes.HANDLE(process._handle)
        )
        if not assigned:
            kernel32.CloseHandle(job)
            return False

        process._pylex_job_handle = job
        process._pylex_job_close = kernel32.CloseHandle
        return True
    except Exception:
        if job and kernel32 is not None:
            try:
                kernel32.CloseHandle(job)
            except Exception:
                pass
        return False


def close_process_job(process):
    """Close a process's Job Object, terminating every remaining member."""
    job = getattr(process, "_pylex_job_handle", None)
    close_handle = getattr(process, "_pylex_job_close", None)
    if not job or close_handle is None:
        return False
    process._pylex_job_handle = None
    process._pylex_job_close = None
    try:
        close_handle(job)
    except OSError:
        return False
    return True


def terminate_process_tree(process):
    """Terminate all descendants using the platform's process-tree primitive."""
    if os.name == "nt":
        if close_process_job(process):
            return True
        if process.poll() is not None:
            return False
        import subprocess

        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
                return True
            except OSError:
                return False

    import signal

    try:
        os.killpg(process.pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        if process.poll() is None:
            try:
                process.kill()
                return True
            except OSError:
                pass
    except OSError:
        if process.poll() is None:
            try:
                process.kill()
                return True
            except OSError:
                pass
    return False
