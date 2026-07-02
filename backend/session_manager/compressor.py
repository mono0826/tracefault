"""对话历史 LLM 压缩器 — 对早期对话进行语义摘要，提取关键信息

单独剥离出来的职责：
    1. 将一段对话历史发送给 LLM，生成结构化摘要
    2. 提取 key_topics / key_entities 等关键信息
    3. LLM 调用失败时提供兜底策略

用法:
    from backend.session_manager.compressor import ConversationCompressor

    compressor = ConversationCompressor()
    summary = compressor.summarize(messages, session_id="sid_001")
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.models.get_models import get_llm_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt 加载
# ---------------------------------------------------------------------------

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / name
    if not path.exists():
        logger.warning("Prompt 文件未找到: %s", path)
        return ""
    return path.read_text(encoding="utf-8")


_COMPRESS_SYSTEM_PROMPT = _load_prompt("conversation_compress.st")


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_json_from_llm(text: str) -> Optional[dict]:
    """从 LLM 响应中提取第一个 JSON 对象，兼容 markdown 代码块包裹。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start: end + 1])
    except json.JSONDecodeError:
        return None


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数：中文字符按 1 token，英文按 4 字符 1 token。"""
    if not text:
        return 0
    chinese = len([c for c in text if "一" <= c <= "鿿"])
    english = len(text) - chinese
    return chinese + english // 4


def estimate_messages_tokens(messages: list[dict]) -> int:
    """估算一组消息的总 token 数。

    每条消息的开销:
        role 标记 (~4 tokens) + content token 数 + 格式开销 (~3 tokens)
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        total += _estimate_tokens(content) + 7  # 4 (role) + 3 (overhead)
    return total


def _format_messages_for_llm(messages: list[dict], max_chars: int = 8000) -> str:
    """将消息列表格式化为 LLM 可读的文本。

    每条格式: [序号] 用户/助手：内容
    """
    history_lines = []
    for i, msg in enumerate(messages):
        label = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")[:500]  # 单条截断防超长
        history_lines.append(f"[{i + 1}] {label}：{content}")

    history_text = "\n".join(history_lines)

    # 控制总长度，超出部分截断
    if len(history_text) > max_chars:
        history_text = history_text[:max_chars] + "\n...（以下内容省略）"

    return history_text


def _fallback_summary(messages: list[dict]) -> dict:
    """LLM 调用失败时的兜底摘要：提取各轮 user 问题作为摘要。"""
    user_questions = [
        m.get("content", "")[:100] for m in messages if m.get("role") == "user"
    ]
    summary_text = "；".join(
        [f"用户提问: {q}" for q in user_questions[:5]]
    )
    if len(user_questions) > 5:
        summary_text += f"…等共{len(user_questions)}轮对话"

    return {
        "summary": summary_text or "（无法生成摘要）",
        "key_topics": [],
        "key_entities": [],
        "timestamp": _now(),
        "message_range": {"start": 0, "end": len(messages) - 1},
    }


# ---------------------------------------------------------------------------
# 压缩器
# ---------------------------------------------------------------------------

class ConversationCompressor:
    """对话历史 LLM 压缩器。

    将一段对话历史（多条 user/assistant 消息）送入 LLM，
    生成结构化摘要，提取其中的关键主题和实体信息。
    """

    def __init__(self, llm=None) -> None:
        """
        参数:
            llm: 可选的 LLM 实例，默认使用 get_llm_model()
        """
        self._llm = llm

    # ------------------------------------------------------------------
    # LLM 懒加载
    # ------------------------------------------------------------------

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm_model()
        return self._llm

    # ------------------------------------------------------------------
    # 核心 API
    # ------------------------------------------------------------------

    def summarize(
        self,
        messages: list[dict],
        session_id: Optional[str] = None,
        llm=None,
    ) -> dict:
        """对一段对话历史进行 LLM 摘要压缩。

        参数:
            messages: 消息列表，每项为 {"role": "user"/"assistant", "content": str}
            session_id: 可选的会话 ID（仅用于日志）
            llm: 可选的 LLM 实例覆盖

        返回:
            {
                "summary": "摘要文本",
                "key_topics": ["主题1", "主题2"],
                "key_entities": ["实体1", "实体2"],
                "timestamp": "2026-...",
                "message_range": {"start": 0, "end": N},
            }

            当 LLM 调用失败时返回兜底摘要（key_topics / key_entities 为空）。
        """
        if not messages:
            return {
                "summary": "",
                "key_topics": [],
                "key_entities": [],
                "timestamp": _now(),
                "message_range": {"start": 0, "end": 0},
            }

        # 没有 prompt 模板时直接走兜底
        if not _COMPRESS_SYSTEM_PROMPT:
            logger.warning("压缩 prompt 模板未找到，使用兜底策略")
            return _fallback_summary(messages)

        # 格式化消息
        history_text = _format_messages_for_llm(messages)

        _llm = llm or self._get_llm()
        sid_info = session_id or "unknown"

        try:
            resp = _llm.invoke([
                ("system", _COMPRESS_SYSTEM_PROMPT.format(
                    history_text=history_text
                )),
                ("human", "请压缩以上对话历史。"),
            ])
            result = _parse_json_from_llm(resp.content)
            if result and result.get("summary"):
                logger.info(
                    "会话 %s 摘要生成成功: %d 条 → %d 字",
                    sid_info, len(messages), len(result["summary"]),
                )
                return {
                    "summary": result["summary"],
                    "key_topics": result.get("key_topics", []),
                    "key_entities": result.get("key_entities", []),
                    "timestamp": _now(),
                    "message_range": {"start": 0, "end": len(messages) - 1},
                }

            logger.warning("LLM 返回 JSON 缺少 summary 字段: %s", resp.content[:200])
        except Exception as exc:
            logger.warning("会话 %s LLM 摘要生成失败: %s，使用兜底策略", sid_info, exc)

        return _fallback_summary(messages)

    def batch_summarize(
        self,
        message_groups: list[tuple[str, list[dict]]],
        llm=None,
    ) -> list[dict]:
        """批量压缩多段对话历史。

        参数:
            message_groups: [(session_id, messages), ...]
            llm: 可选的 LLM 实例覆盖

        返回:
            [summary_dict, ...]  与 summarize() 返回格式一致
        """
        results = []
        for sid, msgs in message_groups:
            results.append(self.summarize(msgs, session_id=sid, llm=llm))
        return results
