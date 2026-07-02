"""会话管理模块 — 对话记录的持久化、读取与 LLM Agent 摘要压缩

主要组件:
    SessionManager        — 会话记录管理器（读写 + compact 压缩）
    ConversationCompressor — LLM 对话历史压缩器（独立的摘要引擎）
"""

from backend.session_manager.manager import SessionManager
from backend.session_manager.compressor import ConversationCompressor

__all__ = ["SessionManager", "ConversationCompressor"]
