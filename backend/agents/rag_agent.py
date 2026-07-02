"""知识库 RAG Agent — 基于知识图谱的意图感知检索问答"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator, Optional

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.get_models import get_llm_model, get_stream_llm_model, get_embeddings_model
from backend.intent_recognition.main import process_query
from backend.session_manager import SessionManager


class RAGAgent:
    """知识库 RAG Agent，先做意图识别 + 查询改写，再检索知识图谱生成回答。"""

    def __init__(self, llm=None, stream_llm=None, embeddings=None):
        self.llm = llm or get_llm_model()
        self.stream_llm = stream_llm or get_stream_llm_model()
        self.embeddings = embeddings or get_embeddings_model()
        self._searcher = None
        self._session_mgr: SessionManager | None = None

    def _ensure_searcher(self):
        if self._searcher is None:
            from backend.search.local_search import LocalSearch
            self._searcher = LocalSearch(self.llm, self.embeddings)
        return self._searcher

    def _ensure_session(self, session_id: str):
        if self._session_mgr is None or self._session_mgr.session_id != session_id:
            self._session_mgr = SessionManager(session_id=session_id)
        return self._session_mgr

    # ---------------------------------------------------------
    #  意图感知 RAG
    # ---------------------------------------------------------

    def intent_rag(self, query: str, session_id: Optional[str] = None) -> dict:
        """意图感知 RAG：意图识别 → 闲聊分流 → 改写 → 检索生成"""
        mgr = None
        history = None
        if session_id:
            mgr = self._ensure_session(session_id)
            mgr.save_current("user", query, metadata={"agent_type": "intent_rag_agent"})
            history = mgr.get_current_history()

        log: list[str] = []

        result = process_query(query, history=history, llm=self.llm, verbose=False)
        log.extend(result["pipeline_log"])
        log.append(f"[意图] {result['intent']} (置信度={result['confidence']:.2f})")

        if result["intent"] == "casual_chat":
            log.append("[动作] 闲聊意图，跳过图谱检索")
            answer = "您好！我是设备故障知识库助手。请询问设备故障现象、原因分析、维修方案等相关问题。"
            if mgr:
                mgr.save_current("assistant", answer)
            return {
                "answer": answer,
                "sources": [],
                "log": log,
                "raw_thinking": "",
                "_intent": result,
            }

        final_query = result["rewritten_query"]
        log.append(f"[改写] 原始: {query}")
        if final_query != query:
            log.append(f"[改写] 改写后: {final_query}")
        if result.get("expansion_terms"):
            log.append(f"[扩展] 关键词: {', '.join(result['expansion_terms'][:5])}")
        log.append(f"[检索] Agent: intent_rag, query: {final_query}")

        try:
            answer = self._ensure_searcher().search(final_query)
            log.append("[生成] 完成")
        except Exception as e:
            log.append(f"[错误] 检索失败: {e}")
            answer = f"抱歉，检索知识图谱时出错：{e}"

        if mgr:
            mgr.save_current("assistant", answer)

        return {
            "answer": answer,
            "sources": [],
            "log": log,
            "raw_thinking": "",
            "_intent": result,
        }

    def intent_rag_stream(self, query: str,
                          session_id: Optional[str] = None) -> Generator[str, None, None]:
        """流式意图感知 RAG"""
        mgr = None
        history = None
        if session_id:
            mgr = self._ensure_session(session_id)
            mgr.save_current("user", query, metadata={"agent_type": "intent_rag_agent"})
            history = mgr.get_current_history()

        result = process_query(query, history=history, llm=self.llm, verbose=False)

        if result["intent"] == "casual_chat":
            answer = "您好！我是设备故障知识库助手。请询问设备故障现象、原因分析、维修方案等相关问题。"
            if mgr:
                mgr.save_current("assistant", answer)
            yield answer
            return

        final_query = result["rewritten_query"]
        try:
            answer_parts = []
            for chunk in self._ensure_searcher().search_stream(final_query):
                answer_parts.append(chunk)
                yield chunk
        except Exception as e:
            yield f"抱歉，检索知识图谱时出错：{e}"
        else:
            if mgr:
                mgr.save_current("assistant", "".join(answer_parts))
