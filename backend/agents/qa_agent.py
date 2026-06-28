"""问答 Agent — 各类 Agent 的检索与生成逻辑（用于测试）

所有 LLM 提示词构建和 Agent 编排都在这里。
前端只调用本模块暴露的接口，不包含任何业务逻辑。
"""

import sys
from pathlib import Path
from typing import Generator

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.get_models import get_llm_model, get_stream_llm_model, get_embeddings_model
from backend.search.local_search import LocalSearch


# =============================================================
#  Agent 实现
# =============================================================

def naive_rag(query: str) -> dict:
    """标准 RAG：直接用 LocalSearch 检索生成"""
    llm = get_llm_model()
    model = get_embeddings_model()
    searcher = LocalSearch(llm, model)
    answer = searcher.search(query)
    return {"answer": answer, "sources": [], "log": [f"[检索] 查询: {query}", "[生成] 完成"]}


def naive_rag_stream(query: str) -> Generator[str, None, None]:
    """流式 RAG"""
    llm = get_stream_llm_model()
    model = get_embeddings_model()
    searcher = LocalSearch(llm, model)
    yield searcher.search(query)


def local_search_agent(query: str) -> dict:
    """知识图谱局部搜索：利用 Neo4j 图谱中的实体、关系、Chunk 生成回答"""
    llm = get_llm_model()
    embeddings = get_embeddings_model()
    searcher = LocalSearch(llm, embeddings)
    try:
        answer = searcher.search(query)
        return {
            "answer": answer,
            "sources": [],
            "log": [
                f"[检索] Agent: local_search",
                f"[检索] 查询: {query}",
                f"[检索] 方式: 知识图谱局部搜索 (Entity→Chunk/Community/Relationship)",
                "[生成] 完成",
            ],
        }
    finally:
        searcher.close()


def local_search_agent_stream(query: str) -> Generator[str, None, None]:
    """知识图谱局部搜索流式"""
    llm = get_stream_llm_model()
    embeddings = get_embeddings_model()
    searcher = LocalSearch(llm, embeddings)
    try:
        answer = searcher.search(query)
        yield answer
    finally:
        searcher.close()
