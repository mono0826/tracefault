"""后端 API 客户端 — 薄调用层

所有业务逻辑（Agent 编排、LLM 提示词构造）都在 backend 包中，
本文件只做导入和透传。
"""

import sys
from pathlib import Path
from typing import Generator

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
import datetime
import streamlit as st

from backend.agents.qa_agent import naive_rag, local_search_agent
from backend.config.settings import PROJECT_ROOT
from backend.config.neo4jdb import get_db_manager


# ===== 问答接口（薄分发层） =====

_AGENT_MAP = {
    "naive_rag_agent": naive_rag,
    "local_search_agent": local_search_agent,
}


def chat_qa(query: str, agent_type: str = "naive_rag_agent",
            session_id: str = None, show_thinking: bool = False,
            use_deeper_tool: bool = False) -> dict:
    """非流式问答 — 透传给 backend.agents.qa_agent"""
    fn = _AGENT_MAP.get(agent_type)
    if fn is None:
        return {"answer": f"未知 Agent: {agent_type}", "sources": [], "execution_log": [], "raw_thinking": ""}
    try:
        if agent_type == "deep_research_agent":
            result = fn(query, show_thinking=show_thinking, use_deeper=use_deeper_tool)
        else:
            result = fn(query)
        # 统一字段名
        return {
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "execution_log": result.get("log", result.get("execution_log", [])),
            "raw_thinking": result.get("thinking", result.get("raw_thinking", "")),
        }
    except Exception as e:
        return {"answer": f"处理出错: {e}", "sources": [], "execution_log": [f"[错误] {e}"], "raw_thinking": ""}


def chat_qa_stream(query: str, agent_type: str = "naive_rag_agent",
                   session_id: str = None, show_thinking: bool = False,
                   use_deeper_tool: bool = False) -> Generator[str, None, None]:
    """流式问答"""
    try:
        if agent_type == "naive_rag_agent":
            from backend.agents.qa_agent import naive_rag_stream
            yield from naive_rag_stream(query)
        elif agent_type == "local_search_agent":
            from backend.agents.qa_agent import local_search_agent_stream
            yield from local_search_agent_stream(query)
    except Exception as e:
        yield f"\n\n生成出错: {e}"


def send_feedback(
    message_id: str,
    query: str,
    is_positive: bool,
    thread_id: str,
    agent_type: str = "naive_rag_agent",
) -> dict:
    """记录反馈到本地 JSONL"""
    try:
        log_dir = PROJECT_ROOT / "data" / "feedback_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "message_id": message_id,
            "query": query,
            "is_positive": is_positive,
            "thread_id": thread_id,
            "agent_type": agent_type,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        with open(log_dir / "feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"status": "success", "action": "高质量反馈已记录" if is_positive else "改进反馈已记录"}
    except Exception as e:
        return {"status": "error", "action": str(e)}


def clear_chat(session_id: str = None):
    """清空聊天状态"""
    st.session_state.processing_lock = False
    st.session_state.messages = []
    st.session_state.execution_log = []
    st.session_state.source_content = None

def search_sources(source_id: str, top_k: int = 1) -> list:
    """按 ID 查询 Chunk 原文（调试用）"""
    try:
        db = get_db_manager()
        result = db.graph.query(
            "MATCH (c:__Chunk__ {id: $id}) RETURN c.text AS content LIMIT $limit",
            params={"id": source_id, "limit": top_k},
        )
        return [{"content": r["content"]} for r in result]
    except Exception as e:
        print(f"查询源文本失败: {e}")
        return []


# ===== 知识图谱构建接口 =====

PIPELINE_STAGES = [
    {"id": "build_graph", "label": "1. 构建图结构"},
    {"id": "build_index", "label": "2. 实体索引与社区"},
    {"id": "build_chunk_index", "label": "3. Chunk 索引"},
]


def check_neo4j() -> tuple:
    """检查 Neo4j 连接状态"""
    try:
        db = get_db_manager()
        db.graph.query("RETURN 1 AS ok")
        return True, f"Neo4j 已连接 ({db.neo4j_uri})"
    except Exception as e:
        return False, str(e)


def get_graph_stats() -> dict:
    """获取知识图谱统计"""
    try:
        db = get_db_manager()
        result = db.graph.query("""
            MATCH (e:`__Entity__`) WITH count(e) AS entities
            MATCH ()-[r]->() WITH entities, count(r) AS total_relations
            MATCH (c:`__Community__`) WITH entities, total_relations, count(c) AS communities
            MATCH (k:`__Chunk__`) WITH entities, total_relations, communities, count(k) AS chunks
            RETURN entities, total_relations, communities, chunks
        """)
        row = result[0] if result else {}
        return {
            "connected": True,
            "entities": row.get("entities", 0),
            "total_relations": row.get("total_relations", 0),
            "communities": row.get("communities", 0),
            "chunks": row.get("chunks", 0),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def run_pipeline(file_paths: list[str] = None, on_status=None, on_log=None) -> dict:
    """执行知识图谱完整构建流程"""
    from backend.integrations.main import KnowledgeGraphProcessor
    if on_log:
        on_log("开始知识图谱构建流程...")
    if on_status:
        on_status("初始化...", 0.0)
    try:
        processor = KnowledgeGraphProcessor()
        processor.process_all(
            file_paths=file_paths,
        )
        stats = get_graph_stats()
        if on_status:
            on_status("构建完成", 1.0)
        return {"success": True, "stats": stats, "stage_results": {"build_graph": True, "build_index": True, "build_chunk_index": True}}
    except Exception as e:
        if on_log:
            on_log(f"构建失败: {e}")
        if on_status:
            on_status("构建失败", 1.0)
        return {"success": False, "error": str(e), "stats": get_graph_stats(), "stage_results": {}}


def run_fast_pipeline(file_paths: list[str] = None, on_status=None, on_log=None) -> dict:
    """快速构建：图结构 → 实体写入 → Chunk 索引（跳过社区检测）"""
    from backend.integrations.build.build_graph import KnowledgeGraphBuilder
    from backend.integrations.build.build_chunk_index import ChunkIndexBuilder
    if on_log:
        on_log("开始快速构建...")
    try:
        if on_status:
            on_status("步骤1: 构建图结构", 0.1)
        builder = KnowledgeGraphBuilder()
        builder.build_base_graph(file_paths=file_paths)

        if on_status:
            on_status("步骤2: 构建Chunk索引", 0.6)
        chunk_builder = ChunkIndexBuilder()
        chunk_builder.process()

        stats = get_graph_stats()
        if on_status:
            on_status("快速构建完成", 1.0)
        return {"success": True, "stats": stats, "stage_results": {"build_graph": True, "build_chunk_index": True}}
    except Exception as e:
        if on_log:
            on_log(f"快速构建失败: {e}")
        return {"success": False, "error": str(e), "stats": get_graph_stats(), "stage_results": {}}
