"""会话管理器 — 完整移植 mini_claude 上下文管理逻辑

上下文管理（对照 mini_claude agent.py）:
  1. Token 估算与追踪
  2. 三层渐进式压缩 pipeline（保留 tool 接口）
  3. 终极压缩 _compact_conversation（LLM 摘要+替换历史）
  4. 自动压缩检查 _check_and_compact

用法:
    mgr = SessionManager(session_id="sid_001")
    mgr.save_current("user", "电机过热")
    mgr.compact()   # 手动触发 LLM 摘要压缩
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config.settings import (
    CHAT_HISTORY_PATH,
    TEXT_WINDOW,
    CONTEXT_RESERVE,
    CONTEXT_AUTO_COMPACT_THRESHOLD,
)
from backend.models.get_models import get_llm_model, count_tokens

logger = logging.getLogger(__name__)

# ============================================================
# mini_claude 常量（对应 agent.py SNIPPABLE_TOOLS / SNIP_THRESHOLD 等）
# ============================================================

# 可截断的工具——这里预定义，后续接入 tool 后使用
SNIPPABLE_TOOLS = {"read_file", "grep_search", "list_files", "run_shell"}
SNIP_PLACEHOLDER = "[Content snipped - re-read if needed]"
SNIP_THRESHOLD = 0.60               # 对应 mini_claude 第二层触发阈值
KEEP_RECENT_RESULTS = 3             # 保留的最远工具结果数
_CHARS_PER_TOKEN_ESTIMATE = 4       # 每 token 对应字符数

# ============================================================
# 内部工具
# ============================================================

_locks: dict[str, threading.Lock] = {}
_lock_global = threading.Lock()

def _session_lock(session_id: str) -> threading.Lock:
    with _lock_global:
        if session_id not in _locks:
            _locks[session_id] = threading.Lock()
        return _locks[session_id]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _session_path(session_id: str) -> Path:
    return (CHAT_HISTORY_PATH / session_id).with_suffix(".json")

def _build_session(session_id: str) -> dict:
    now = _now()
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "estimated_tokens": 0,
        "compression_count": 0,
        "metadata": {"compressed": False},
        "messages": [],
    }

def _estimate_messages_tokens(messages: list) -> int:
    """估算一组消息的总 token 数（使用 count_tokens + 格式开销）。"""
    total = 0
    for m in messages:
        content = m.get("content", "") or ""
        total += count_tokens(content) + 7          # 7 = role + 格式开销
    return total


# ============================================================
# SessionManager — 完整移植 mini_claude 上下文管理
# ============================================================

class SessionManager:
    """会话管理器 + 三层上下文压缩（保留 tool 接口）。"""

    def __init__(
        self,
        history_path: Optional[Path] = None,
        session_id: Optional[str] = None,
        llm=None,
    ) -> None:
        self._history_path = (history_path or CHAT_HISTORY_PATH).resolve()
        self._history_path.mkdir(parents=True, exist_ok=True)
        self._current_session_id: Optional[str] = session_id
        self._llm = llm

        # ------ mini_claude 追踪字段 ------
        self.last_input_token_count = 0
        self.last_api_call_time = 0.0
        # ------ 压缩摘要（内存中，不写入 JSON）------
        self._summary: str | None = None

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def history_path(self) -> Path:
        return self._history_path

    @property
    def session_id(self) -> Optional[str]:
        return self._current_session_id

    def use_session(self, session_id: str) -> SessionManager:
        self._current_session_id = session_id
        return self

    def _require_current_session(self) -> str:
        sid = self._current_session_id
        if sid is None:
            raise RuntimeError("当前会话未设置，请先调用 use_session(session_id)")
        return sid

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm_model()
        return self._llm

    @staticmethod
    def effective_window() -> int:
        """有效上下文窗口（对应 mini_claude effective_window）。"""
        return TEXT_WINDOW - CONTEXT_RESERVE

    # ------------------------------------------------------------------
    # token 估算（对应 mini_claude _estimate_context_tokens_from_history）
    # ------------------------------------------------------------------

    def _recalc_estimated_tokens(self, data: dict) -> int:
        return _estimate_messages_tokens(data.get("messages", []))

    def _effective_tokens(self, session_id: str) -> int:
        """实际生效的 token 数：基于 get_history() 返回的消息。"""
        messages = self.get_history(session_id)
        return _estimate_messages_tokens(messages)

    def get_context_utilization(self, session_id: str) -> float:
        """上下文利用率：基于实际生效的消息（摘要替代旧消息）。"""
        tokens = self._effective_tokens(session_id)
        eff = self.effective_window()
        return tokens / eff if eff > 0 else 0.0

    def get_current_context_utilization(self) -> float:
        return self.get_context_utilization(self._require_current_session())

    @staticmethod
    def _clean_surrogates(obj: Any) -> Any:
        """递归清洗数据中的代理项字符（Windows 管道编码问题）。"""
        if isinstance(obj, str):
            return obj.encode("utf-8", errors="ignore").decode("utf-8")
        if isinstance(obj, dict):
            return {k: SessionManager._clean_surrogates(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [SessionManager._clean_surrogates(v) for v in obj]
        return obj

    # ------------------------------------------------------------------
    # 基础读写
    # ------------------------------------------------------------------

    def _read(self, session_id: str) -> dict:
        path = _session_path(session_id)
        if not path.exists():
            return _build_session(session_id)
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("读取会话文件 %s 失败: %s", path, exc)
            return _build_session(session_id)

    def _write(self, session_id: str, data: dict) -> None:
        path = _session_path(session_id)
        tmp = path.with_suffix(".tmp")
        # 清洗数据：去除代理项字符，防止 Windows 管道引入的编码问题
        data = self._clean_surrogates(data)
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except OSError as exc:
            logger.error("写入会话文件 %s 失败: %s", path, exc)
            tmp.unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # 公共 API — 读写
    # ------------------------------------------------------------------

    def save_message(self, session_id: str, role: str, content: str,
                     metadata: Optional[dict] = None) -> dict:
        if role not in ("user", "assistant"):
            raise ValueError("role 必须是 'user' 或 'assistant'")

        lock = _session_lock(session_id)
        with lock:
            data = self._read(session_id)
            if data["message_count"] == 0 and metadata:
                data["metadata"].update(metadata)

            data["messages"].append({
                "role": role, "content": content, "timestamp": _now(),
            })
            data["message_count"] = len(data["messages"])
            data["updated_at"] = _now()
            self._write(session_id, data)

            # 对应 mini_claude 每次消息后压缩检查
            self._check_and_compact(session_id, data)

        return data

    def save_current(self, role: str, content: str,
                     metadata: Optional[dict] = None) -> dict:
        return self.save_message(self._require_current_session(), role, content, metadata)

    def get_history(self, session_id: str) -> list[dict]:
        """获取消息列表。

        有摘要时：返回 [摘要] + [compact 之后的新消息]（摘要替代旧消息）
        无摘要时：返回全部消息
        """
        data = self._read(session_id)
        messages = data.get("messages", [])
        if not self._summary:
            return messages

        # 有摘要：只返回摘要 + compact 之后的消息
        compact_idx = data.get("metadata", {}).get("compact_at_message_count", 0)
        recent = messages[compact_idx:]
        return [
            {"role": "system", "content": f"[对话历史摘要]\n{self._summary}",
             "is_summary": True},
        ] + recent

    def get_current_history(self) -> list[dict]:
        return self.get_history(self._require_current_session())

    def get_recent_rounds(self, session_id: str, max_rounds: int = 5) -> list[dict]:
        messages = self.get_history(session_id)
        if max_rounds <= 0:
            return []
        rounds, count = [], 0
        for msg in reversed(messages):
            rounds.append(msg)
            if msg["role"] == "user":
                count += 1
                if count >= max_rounds:
                    break
        rounds.reverse()
        return rounds

    def get_session_info(self, session_id: str) -> Optional[dict]:
        path = _session_path(session_id)
        if not path.exists():
            return None
        data = self._read(session_id)
        # 有效 tokens 基于 get_history（摘要替代旧消息）
        effective_tokens = self._effective_tokens(session_id)
        ef = self.effective_window()
        return {
            "session_id": data["session_id"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "message_count": data["message_count"],
            "estimated_tokens": effective_tokens,
            "context_utilization": round(effective_tokens / ef, 3) if ef > 0 else 0.0,
            "compression_count": data.get("compression_count", 0),
            "metadata": data["metadata"],
        }

    def get_current_info(self) -> Optional[dict]:
        return self.get_session_info(self._require_current_session())

    def delete_session(self, session_id: str) -> bool:
        path = _session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self, sort_by: str = "updated_at", reverse: bool = True) -> list[dict]:
        sessions = []
        for path in sorted(self._history_path.iterdir()):
            if path.suffix != ".json":
                continue
            info = self.get_session_info(path.stem)
            if info:
                sessions.append(info)
        valid = {"created_at", "updated_at", "message_count", "estimated_tokens"}
        key = sort_by if sort_by in valid else "updated_at"
        sessions.sort(key=lambda s: s.get(key) or 0, reverse=reverse)
        return sessions

    # ================================================================
    # mini_claude 三层压缩 pipeline（保留 tool 接口供后续使用）
    #
    # 对应 agent.py _run_compression_pipeline → _budget / _snip / _microcompact
    # ================================================================

    def _run_compression_pipeline(self, session_id: str, data: dict) -> None:
        """三层渐进式压缩（对应 mini_claude _run_compression_pipeline）。

        当前未接入 tool 调用，Tier 1/2/3 暂时不生效；
        后续接入 tool 后，各层会自动启用。
        """
        utilization = data.get("estimated_tokens", 0) / self.effective_window() if self.effective_window() else 0

        # Tier 1: 预算 tool 结果（>= 50%）
        self._budget_tool_results(data, utilization)

        # Tier 2: 裁剪陈旧结果（>= 60%）
        self._snip_stale_results(data, utilization)

        # Tier 3: 空闲时微压缩（>= 5min 空闲）
        self._microcompact(data, utilization)

    # ---- Tier 1（对应 mini_claude _budget_tool_results_anthropic）----

    def _budget_tool_results(self, data: dict, utilization: float) -> None:
        """预算 tool 结果：当上下文 >50%，对 tool_result 做对称截断。"""
        if utilization < 0.5:
            return
        budget = 15000 if utilization > 0.7 else 30000
        for msg in data.get("messages", []):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                if len(content) > budget:
                    keep = (budget - 80) // 2
                    msg["content"] = (
                        content[:keep]
                        + f"\n\n[... budgeted: {len(content) - keep * 2} chars truncated ...]\n\n"
                        + content[-keep:]
                    )
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        txt = block.get("content", "")
                        if isinstance(txt, str) and len(txt) > budget:
                            keep = (budget - 80) // 2
                            block["content"] = (
                                txt[:keep]
                                + f"\n\n[... budgeted: {len(txt) - keep * 2} chars truncated ...]\n\n"
                                + txt[-keep:]
                            )

    # ---- Tier 2（对应 mini_claude _snip_stale_results_anthropic）----

    def _snip_stale_results(self, data: dict, utilization: float) -> None:
        """裁剪陈旧结果：>=60% 时，将可截断工具的结果替换为占位符。"""
        if utilization < SNIP_THRESHOLD:
            return

        messages = data.get("messages", [])
        tool_results = []
        for mi, msg in enumerate(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for bi, block in enumerate(content):
                if (isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and isinstance(block.get("content"), str)
                    and block["content"] != SNIP_PLACEHOLDER):
                    tool_use_id = block.get("tool_use_id")
                    # 这里预留 tool 查找接口，后续接入
                    tool_results.append({
                        "mi": mi, "bi": bi, "tool_use_id": tool_use_id,
                    })

        # 只保留最近 KEEP_RECENT_RESULTS 个结果
        if len(tool_results) <= KEEP_RECENT_RESULTS:
            return
        for entry in tool_results[:-KEEP_RECENT_RESULTS]:
            block = messages[entry["mi"]]["content"][entry["bi"]]
            if block.get("type") == "tool_result":
                block["content"] = SNIP_PLACEHOLDER

    # ---- Tier 3（对应 mini_claude _microcompact_anthropic）----

    def _microcompact(self, data: dict, utilization: float) -> None:
        """微压缩：清理剩余陈旧结果（当前预留）。"""
        pass

    # ================================================================
    # 核心：_check_and_compact + _compact_conversation
    # 完全照搬 mini_claude agent.py 的对应逻辑
    # ================================================================

    def _check_and_compact(self, session_id: str, data: dict) -> bool:
        """每次保存消息后检查上下文利用率，超过阈值则自动压缩。

        对应 mini_claude:
            async def _check_and_compact(self):
                if self.last_input_token_count > self.effective_window * 0.85:
                    await self._compact_conversation()
        """
        # 基于 get_history 的有效 token（摘要替代旧消息）
        tokens = self._effective_tokens(session_id)
        self.last_input_token_count = tokens
        eff = self.effective_window()
        if eff <= 0:
            return False
        ratio = tokens / eff
        if ratio >= CONTEXT_AUTO_COMPACT_THRESHOLD:
            logger.info("上下文利用率 %.1f%% ≥ %.0f%%，自动压缩",
                        ratio * 100, CONTEXT_AUTO_COMPACT_THRESHOLD * 100)
            return self._compact_conversation(session_id, data)
        return False

    # ------------------------------------------------------------------
    # compact() — 对外手动压缩入口
    # ------------------------------------------------------------------

    def compact(self, llm=None) -> bool:
        """手动压缩当前会话（对应 mini_claude compact()）。"""
        sid = self._require_current_session()
        return self.compress_session(sid, llm=llm)

    def compress_session(self, session_id: str, llm=None) -> bool:
        """压缩指定会话 — 摘要存在内存，不修改 JSON 中的消息。

        1. 至少需要 4 条消息
        2. 全部消息发送给 LLM 生成摘要
        3. 摘要存入 self._summary（内存，不落盘）
        4. 只记录 compression_count 到文件
        """
        lock = _session_lock(session_id)
        with lock:
            data = self._read(session_id)
            messages = data.get("messages", [])
            if len(messages) < 4:
                logger.info("会话 %s 消息数 %d < 4，跳过压缩", session_id, len(messages))
                return False

            # 调用 LLM 生成摘要
            _llm = llm or self._get_llm()
            summary_prompt = (
                "Summarize the conversation so far in a concise paragraph, "
                "preserving key decisions, technical details, "
                "and context needed to continue the work."
            )
            llm_msgs = [(m["role"], m["content"]) for m in messages]
            llm_msgs[-1] = ("user", summary_prompt)

            try:
                resp = _llm.invoke(llm_msgs)
                summary_text = resp.content
            except Exception as e:
                logger.warning("LLM 摘要失败: %s，使用兜底", e)
                user_qs = [m["content"][:100] for m in messages if m["role"] == "user"]
                summary_text = "；".join([f"用户提问: {q}" for q in user_qs[:5]])

            # 摘要存内存，不写进 messages
            self._summary = summary_text

            # compact 位置：保留最后 1 轮（user+assistant）完整
            # 对应 mini_claude 保留最后一条 user 消息
            compact_at = len(messages) - 2 if len(messages) >= 2 else 0
            data["metadata"]["compact_at_message_count"] = compact_at
            data["compression_count"] = data.get("compression_count", 0) + 1
            data["metadata"]["compressed"] = True
            data["updated_at"] = _now()
            self._write(session_id, data)

            logger.info(
                "会话 %s 压缩完成 (第 %d 次): %d 条消息 → 摘要已存入内存",
                session_id, data["compression_count"], len(messages),
            )
            return True

    # ================================================================
    # 清理 & 统计
    # ================================================================

    def clean_expired(self, max_days: int = 30, dry_run: bool = False) -> list[str]:
        now = datetime.now(timezone.utc)
        expired = []
        for path in list(self._history_path.iterdir()):
            if path.suffix != ".json":
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if (now - mtime).days > max_days:
                expired.append(path.stem)
        if not dry_run:
            for sid in expired:
                self.delete_session(sid)
        return expired

    def clean_all(self) -> int:
        count = 0
        for path in list(self._history_path.iterdir()):
            if path.suffix == ".json":
                path.unlink()
                count += 1
        return count

    def total_sessions(self) -> int:
        return len(self.list_sessions())

    def total_messages(self) -> int:
        return sum(info.get("message_count", 0) for info in self.list_sessions())

    def disk_usage(self) -> dict:
        total, files = 0, 0
        for path in self._history_path.iterdir():
            if path.suffix == ".json":
                total += path.stat().st_size
                files += 1
        for u in ("B", "KB", "MB", "GB"):
            if total < 1024:
                return {"path": str(self._history_path), "size_bytes": total,
                        "size_human": f"{total:.1f} {u}", "file_count": files}
            total /= 1024
        return {"path": str(self._history_path), "size_bytes": total,
                "size_human": f"{total:.1f} TB", "file_count": files}
