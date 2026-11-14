"""اجرای کد در پردازه فرزند با محدودیت زمانی."""
import subprocess
import sys
import tempfile
from pathlib import Path

def run_source(source, timeout=10):
    """کد را اجرا کرده و stdout، stderr و کد خروج را برمی‌گرداند.

    توجه: این روش sandbox امنیتی محسوب نمی‌شود.
    """
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as f:
            f.write(source)
            path = Path(f.name)
        result = subprocess.run([sys.executable, str(path)], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"اجرای برنامه پس از {timeout} ثانیه متوقف شد.", -1
    finally:
        if path:
            path.unlink(missing_ok=True)
