"""将后端 Rich Console / print 输出桥接到 Streamlit 终端面板"""

from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from typing import Callable, Optional

from rich.console import Console

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _clean_line(text: str) -> str:
    text = _ANSI_RE.sub("", text).replace("\r", "").strip()
    return text


class PipelineLogWriter:
    """把 stdout/stderr / Rich 输出按行转发到 on_log"""

    def __init__(self, on_log: Callable[[str], None]):
        self._on_log = on_log
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        # Rich Progress 用 \r 刷新同一行，不当作新日志
        if "\r" in text and "\n" not in text:
            self._buffer = text.split("\r")[-1]
            return len(text)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            cleaned = _clean_line(line)
            if cleaned:
                try:
                    self._on_log(cleaned)
                except Exception:
                    pass  # Streamlit 会话已结束，忽略
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            cleaned = _clean_line(self._buffer)
            if cleaned:
                self._on_log(cleaned)
            self._buffer = ""

    def isatty(self) -> bool:
        return False


def _collect_console_holders(processor) -> list:
    holders = [
        processor,
        processor.graph_builder,
        processor.index_community_builder,
        processor.chunk_index_builder,
        processor.incremental_updater,
    ]
    iu = processor.incremental_updater
    for attr in ("updater", "validator", "edit_manager", "embedding_manager", "scheduler"):
        if hasattr(iu, attr):
            holders.append(getattr(iu, attr))
    return holders


@contextmanager
def bridge_pipeline_logs(processor, on_log: Optional[Callable[[str], None]]):
    """运行构建时捕获后端终端输出并转发到 UI 回调"""
    if not on_log:
        yield
        return

    writer = PipelineLogWriter(on_log)
    console = Console(
        file=writer,
        force_terminal=False,
        color_system=None,
        width=100,
        legacy_windows=False,
    )

    holders = _collect_console_holders(processor)
    old_consoles = {id(h): h.console for h in holders if hasattr(h, "console")}
    for h in holders:
        if hasattr(h, "console"):
            h.console = console

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = writer
    sys.stderr = writer
    try:
        yield
    finally:
        writer.flush()
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        for h in holders:
            if hasattr(h, "console") and id(h) in old_consoles:
                h.console = old_consoles[id(h)]
