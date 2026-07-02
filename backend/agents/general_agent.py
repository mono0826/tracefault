"""通用对话 Agent — 基于 SessionManager 做上下文管理，不依赖知识图谱"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator, Optional

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.get_models import get_llm_model, get_stream_llm_model
from backend.session_manager import SessionManager


_SYSTEM_PROMPT = "你是一个设备故障诊断专家，请专业地回答用户问题。"


class GeneralAgent:
    """通用对话 Agent，基于 SessionManager 管理上下文，LLM 直接回答。

    不依赖知识图谱，适用于闲聊、常识问答、简单咨询等场景。
    """

    def __init__(self, llm=None, stream_llm=None):
        self.llm = llm or get_llm_model()
        self.stream_llm = stream_llm or get_stream_llm_model()
        self._session_mgr: SessionManager | None = None

    def _ensure_session(self, session_id: str | None) -> SessionManager:
        """初始化或复用 SessionManager 实例。"""
        if self._session_mgr is None or (
            session_id and self._session_mgr.session_id != session_id
        ):
            self._session_mgr = SessionManager()
            if session_id:
                self._session_mgr.use_session(session_id)
        return self._session_mgr

    def _build_messages(self, mgr: SessionManager) -> list:
        """构建 LLM 消息列表（system + history 自动含摘要）。"""
        msgs = [("system", _SYSTEM_PROMPT)]
        for m in mgr.get_current_history():
            msgs.append((m["role"], m["content"]))
        return msgs

    # ---------------------------------------------------------
    #  非流式对话
    # ---------------------------------------------------------

    def chat(self, query: str, session_id: str | None = None) -> dict:
        """通用对话，不依赖知识图谱。

        参数:
            query: 用户输入
            session_id: 会话 ID（不传则默认单次会话）

        返回:
            {"answer": str, "sources": [], "log": [str, ...]}
        """
        mgr = self._ensure_session(session_id)
        mgr.save_current("user", query)

        msgs = self._build_messages(mgr)

        log = [f"[通用对话] 输入: {query}"]

        try:
            answer = self.llm.invoke(msgs).content
            log.append("[生成] 完成")
        except Exception as e:
            answer = f"抱歉，回答时出现错误：{e}"
            log.append(f"[错误] {e}")

        mgr.save_current("assistant", answer)
        return {"answer": answer, "sources": [], "log": log}

    # ---------------------------------------------------------
    #  流式对话
    # ---------------------------------------------------------

    def chat_stream(self, query: str, session_id: str | None = None) -> Generator[str, None, None]:
        """流式通用对话。

        参数:
            query: 用户输入
            session_id: 会话 ID

        产出:
            str: LLM 逐 token 回复
        """
        mgr = self._ensure_session(session_id)
        mgr.save_current("user", query)

        msgs = self._build_messages(mgr)

        try:
            answer_parts = []
            for chunk in self.stream_llm.stream(msgs):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                answer_parts.append(content)
                yield content
        except Exception as e:
            yield f"抱歉，回答时出现错误：{e}"
        else:
            mgr.save_current("assistant", "".join(answer_parts))
