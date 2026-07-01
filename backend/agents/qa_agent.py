"""问答 Agent — 各类 Agent 的检索与生成逻辑

所有 LLM 提示词构建和 Agent 编排都在这里。
前端只调用本模块暴露的接口，不包含任何业务逻辑。

用法：
    # 方式一：使用默认单例
    from backend.agents.qa_agent import qa_agent
    result = qa_agent.intent_rag("离心压缩机振动超标怎么办？")

    # 方式二：使用模块级便捷函数（向后兼容）
    from backend.agents.qa_agent import intent_rag
    result = intent_rag("离心压缩机振动超标怎么办？")

    # 方式三：自定义实例
    from backend.agents.qa_agent import QAAgent
    agent = QAAgent(llm=my_llm, embeddings=my_emb)
    result = agent.intent_rag("...")
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator, Optional

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.get_models import get_llm_model, get_stream_llm_model, get_embeddings_model
from backend.intent_recognition.main import process_query


class QAAgent:
    """问答 Agent 类，统一管理 LLM 和 Embedding 实例。"""

    def __init__(self, llm=None, stream_llm=None, embeddings=None):
        self.llm = llm or get_llm_model()
        self.stream_llm = stream_llm or get_stream_llm_model()
        self.embeddings = embeddings or get_embeddings_model()

    # ---------------------------------------------------------
    #  标准 RAG
    # ---------------------------------------------------------

    def naive_rag(self, query: str) -> dict:
        """标准 RAG：直接用 LocalSearch 检索生成"""
        from backend.search.local_search import LocalSearch
        searcher = LocalSearch(self.llm, self.embeddings)
        answer = searcher.search(query)
        return {
            "answer": answer,
            "sources": [],
            "log": [f"[检索] 查询: {query}", "[生成] 完成"],
        }

    def naive_rag_stream(self, query: str) -> Generator[str, None, None]:
        """流式 RAG"""
        from backend.search.local_search import LocalSearch
        searcher = LocalSearch(self.stream_llm, self.embeddings)
        yield searcher.search(query)

    # ---------------------------------------------------------
    #  局部搜索
    # ---------------------------------------------------------

    def local_search(self, query: str) -> dict:
        """知识图谱局部搜索"""
        from backend.search.local_search import LocalSearch
        searcher = LocalSearch(self.llm, self.embeddings)
        try:
            answer = searcher.search(query)
            return {
                "answer": answer,
                "sources": [],
                "log": [
                    "[检索] Agent: local_search",
                    f"[检索] 查询: {query}",
                    "[检索] 方式: 知识图谱局部搜索 (Entity→Chunk/Community/Relationship)",
                    "[生成] 完成",
                ],
            }
        finally:
            searcher.close()

    def local_search_stream(self, query: str) -> Generator[str, None, None]:
        """局部搜索流式"""
        from backend.search.local_search import LocalSearch
        searcher = LocalSearch(self.stream_llm, self.embeddings)
        try:
            yield searcher.search(query)
        finally:
            searcher.close()

    # ---------------------------------------------------------
    #  意图感知 RAG
    # ---------------------------------------------------------

    def intent_rag(self, query: str, history: Optional[list] = None) -> dict:
        """
        意图感知 RAG：先做意图识别 + 查询改写，再按意图分流。

        流程：
          1. process_query 做归一化 → 意图分类 → 改写
          2. 闲聊意图 → 直接返回友好提示
          3. 设备查询 → 用改写后的 query 做 LocalSearch
        """
        log: list[str] = []

        # Step 1: 意图识别 + 改写
        result = process_query(query, history=history, llm=self.llm, verbose=False)
        log.extend(result["pipeline_log"])
        log.append(f"[意图] {result['intent']} (置信度={result['confidence']:.2f})")

        # Step 2: 闲聊分流
        if result["intent"] == "casual_chat":
            log.append("[动作] 闲聊意图，跳过图谱检索")
            return {
                "answer": "您好！我是设备故障知识库助手。请询问设备故障现象、原因分析、维修方案等相关问题。",
                "sources": [],
                "log": log,
                "raw_thinking": "",
                "_intent": result,
            }

        # Step 3: 设备查询 — 用改写后的 query 检索
        final_query = result["rewritten_query"]
        log.append(f"[改写] 原始: {query}")
        if final_query != query:
            log.append(f"[改写] 改写后: {final_query}")
        if result.get("expansion_terms"):
            log.append(f"[扩展] 关键词: {', '.join(result['expansion_terms'][:5])}")

        log.append(f"[检索] Agent: intent_rag, query: {final_query}")

        try:
            from backend.search.local_search import LocalSearch
            searcher = LocalSearch(self.llm, self.embeddings)
            answer = searcher.search(final_query)
            log.append("[生成] 完成")
            return {
                "answer": answer,
                "sources": [],
                "log": log,
                "raw_thinking": "",
                "_intent": result,
            }
        except Exception as e:
            log.append(f"[错误] 检索失败: {e}")
            return {
                "answer": f"抱歉，检索知识图谱时出错：{e}",
                "sources": [],
                "log": log,
                "raw_thinking": "",
                "_intent": result,
            }

    def intent_rag_stream(self, query: str, history: Optional[list] = None) -> Generator[str, None, None]:
        """
        意图感知 RAG 流式版本。
        闲聊意图直接返回一句话；设备查询做检索后返回结果。
        """
        # 意图识别（用非流式 LLM，快）
        result = process_query(query, history=history, llm=self.llm, verbose=False)

        if result["intent"] == "casual_chat":
            yield "您好！我是设备故障知识库助手。请询问设备故障现象、原因分析、维修方案等相关问题。"
            return

        final_query = result["rewritten_query"]
        try:
            from backend.search.local_search import LocalSearch
            searcher = LocalSearch(self.stream_llm, self.embeddings)
            yield searcher.search(final_query)
        except Exception as e:
            yield f"抱歉，检索知识图谱时出错：{e}"


# =============================================================
#  默认单例 & 模块级便捷函数（向后兼容）
# =============================================================

qa_agent = QAAgent()

naive_rag = qa_agent.naive_rag
naive_rag_stream = qa_agent.naive_rag_stream
local_search_agent = qa_agent.local_search
local_search_agent_stream = qa_agent.local_search_stream
intent_rag = qa_agent.intent_rag
intent_rag_stream = qa_agent.intent_rag_stream

AGENT_REGISTRY = {
    "naive_rag_agent": {
        "fn": naive_rag,
        "stream_fn": naive_rag_stream,
        "description": "标准 RAG，直接检索图谱生成回答",
    },
    "local_search_agent": {
        "fn": local_search_agent,
        "stream_fn": local_search_agent_stream,
        "description": "局部搜索，利用实体/关系/Chunk 生成回答",
    },
    "intent_rag_agent": {
        "fn": intent_rag,
        "stream_fn": intent_rag_stream,
        "description": "意图感知 RAG，先识别意图再决定是否检索",
    },
}
