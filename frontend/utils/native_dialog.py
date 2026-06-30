"""在独立子进程中打开系统文件/文件夹对话框，避免 Streamlit 线程下 Tcl_AsyncDelete 报错"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import List, Optional

_DOC_FILETYPES = [
    ("文档文件", "*.pdf *.docx *.md *.txt"),
    ("PDF", "*.pdf"),
    ("Word", "*.docx"),
    ("Markdown", "*.md"),
    ("文本", "*.txt"),
    ("所有文件", "*.*"),
]

_FOLDER_SCRIPT = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
path = filedialog.askdirectory()
root.update_idletasks()
root.quit()
root.destroy()
if path:
    print(path, end="")
"""

_FILES_SCRIPT = """
import json
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
files = filedialog.askopenfilenames(
    title="选择文档文件",
    filetypes={filetypes!r},
)
root.update_idletasks()
root.quit()
root.destroy()
print(json.dumps(list(files)), end="")
"""


def _run_subprocess(code: str, timeout: int = 600) -> subprocess.CompletedProcess:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        **kwargs,
    )


def pick_folder() -> Optional[str]:
    """弹出系统文件夹选择对话框，返回路径或 None"""
    try:
        result = _run_subprocess(_FOLDER_SCRIPT)
        if result.returncode != 0 and result.stderr:
            raise RuntimeError(result.stderr.strip())
        path = result.stdout.strip()
        return path or None
    except subprocess.TimeoutExpired:
        raise RuntimeError("选择文件夹超时")
    except Exception as e:
        raise RuntimeError(f"打开文件夹对话框失败: {e}") from e


def pick_files() -> List[str]:
    """弹出系统文件选择对话框（可多选），返回绝对路径列表"""
    code = _FILES_SCRIPT.format(filetypes=_DOC_FILETYPES)
    try:
        result = _run_subprocess(code)
        if result.returncode != 0 and result.stderr:
            raise RuntimeError(result.stderr.strip())
        raw = result.stdout.strip()
        if not raw:
            return []
        files = json.loads(raw)
        return [str(p) for p in files if p]
    except subprocess.TimeoutExpired:
        raise RuntimeError("选择文件超时")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"解析文件选择结果失败: {e}") from e
    except Exception as e:
        raise RuntimeError(f"打开文件对话框失败: {e}") from e
