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
import uuid
import streamlit as st

from frontend.common.constants import AGENT_OPTIONS
from frontend.utils.helpers import generate_session_id
from backend.config.settings import PROJECT_ROOT, CHAT_HISTORY_PATH
from backend.config.neo4jdb import get_db_manager


# ===== 历史会话 =====

_HISTORY_LIST_LIMIT = 20


def _session_json_path(session_id: str) -> Path:
    return CHAT_HISTORY_PATH / f"{session_id}.json"


def _read_session_json(session_id: str) -> dict | None:
    """直接读取 CHAT_HISTORY_PATH 下的会话 JSON"""
    path = _session_json_path(session_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _format_session_time(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return iso_str[:16]


def _session_title(messages: list[dict]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            text = (msg.get("content") or "").strip()
            if text:
                return text[:16] + ("…" if len(text) > 16 else "")
    return "新对话"


def _to_frontend_messages(raw_messages: list[dict]) -> list[dict]:
    """JSON 消息 → 前端展示格式（含 system 摘要）"""
    result = []
    for msg in raw_messages:
        role = msg.get("role", "")
        content = msg.get("content") or ""
        if role not in ("user", "assistant", "system"):
            continue
        item = {
            "role": role,
            "content": content,
            "message_id": str(uuid.uuid4()),
        }
        if role == "system" or msg.get("is_summary"):
            item["role"] = "system"
            item["is_summary"] = True
        result.append(item)
    return result


def list_chat_sessions(limit: int = _HISTORY_LIST_LIMIT) -> list[dict]:
    """列出历史会话（含标题、时间）"""
    from backend.session_manager import SessionManager

    mgr = SessionManager()
    sessions = mgr.list_sessions()[:limit]
    enriched = []
    for info in sessions:
        sid = info["session_id"]
        data = _read_session_json(sid)
        messages = data.get("messages", []) if data else []
        enriched.append({
            **info,
            "title": _session_title(messages),
            "time_label": _format_session_time(info.get("updated_at", "")),
        })
    return enriched


def load_chat_session(session_id: str) -> bool:
    """加载历史会话到 session_state，并恢复 agent_type"""
    data = _read_session_json(session_id)
    if not data:
        return False

    agent_type = data.get("metadata", {}).get("agent_type", "general_agent")
    if agent_type not in AGENT_OPTIONS:
        agent_type = "general_agent"

    st.session_state.session_id = session_id
    st.session_state._pending_agent_type = agent_type
    st.session_state.messages = _to_frontend_messages(data.get("messages", []))
    st.session_state.execution_log = []
    st.session_state.feedback_given = set()
    st.session_state.processing_lock = False
    st.session_state.source_content = None
    return True


def delete_chat_session(session_id: str) -> bool:
    """删除历史会话 JSON"""
    from backend.session_manager import SessionManager

    return SessionManager().delete_session(session_id)


def start_new_chat_session():
    """开始新对话（新 session_id，清空界面状态）"""
    st.session_state.session_id = generate_session_id()
    st.session_state.messages = []
    st.session_state.execution_log = []
    st.session_state.feedback_given = set()
    st.session_state.processing_lock = False
    st.session_state.source_content = None


# ===== 问答接口（薄分发层） =====

def _get_agent_fn(agent_type: str):
    """延迟导入并获取 Agent 调用函数"""
    from backend.agents import chat, intent_rag
    _MAP = {
        "general_agent": chat,
        "intent_rag_agent": intent_rag,
    }
    return _MAP.get(agent_type)


def chat_qa(query: str, agent_type: str = "general_agent",
            session_id: str = None, show_thinking: bool = False,
            use_deeper_tool: bool = False) -> dict:
    """非流式问答 — 透传给 backend Agent"""
    if agent_type == "deep_research_agent":
        from backend.search.tool.deep_research_tool import DeepResearchTool
        try:
            result = DeepResearchTool().research(query, show_thinking=show_thinking, use_deeper=use_deeper_tool)
        except Exception as e:
            return {"answer": f"处理出错: {e}", "sources": [], "execution_log": [f"[错误] {e}"], "raw_thinking": ""}
        return {"answer": result.get("answer", ""), "sources": result.get("sources", []),
                "execution_log": result.get("log", []), "raw_thinking": result.get("thinking", "")}

    fn = _get_agent_fn(agent_type)
    if fn is None:
        return {"answer": f"未知 Agent: {agent_type}", "sources": [], "execution_log": [], "raw_thinking": ""}
    try:
        result = fn(query, session_id=session_id)
        return {
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "execution_log": result.get("log", result.get("execution_log", [])),
            "raw_thinking": result.get("thinking", result.get("raw_thinking", "")),
        }
    except Exception as e:
        return {"answer": f"处理出错: {e}", "sources": [], "execution_log": [f"[错误] {e}"], "raw_thinking": ""}


def chat_qa_stream(query: str, agent_type: str = "general_agent",
                   session_id: str = None, show_thinking: bool = False,
                   use_deeper_tool: bool = False,
                   history: list | None = None) -> Generator[str, None, None]:
    """流式问答 — 按 Agent 注册表分发"""
    if agent_type == "deep_research_agent":
        yield "深度研究 Agent 暂不支持流式输出，请在侧栏关闭流式模式或切换其他 Agent。"
        return
    from backend.agents import AGENT_REGISTRY
    entry = AGENT_REGISTRY.get(agent_type)
    if not entry or "stream_fn" not in entry:
        yield f"未知或不支持流式的 Agent: {agent_type}"
        return
    try:
        stream_fn = entry["stream_fn"]
        yield from stream_fn(query, session_id=session_id)
    except Exception as e:
        yield f"\n\n生成出错: {e}"


def send_feedback(
    message_id: str,
    query: str,
    is_positive: bool,
    thread_id: str,
    agent_type: str = "general_agent",
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
    """开始新对话"""
    start_new_chat_session()

def search_sources(source_id: str, top_k: int = 1) -> list:
    """按 ID 查询 Chunk 原文（调试用）"""
    try:
        if not check_has_graph():
            return []
        db = get_db_manager()
        result = db.graph.query(
            "MATCH (c:__Chunk__ {id: $id}) RETURN c.text AS content LIMIT $limit",
            params={"id": source_id, "limit": top_k},
        )
        return [{"content": r["content"]} for r in result]
    except Exception as e:
        print(f"查询源文本失败: {e}")
        return []


def get_graph_data(limit: int = 300) -> dict:
    """获取知识图谱节点和关系数据用于可视化"""
    try:
        if not check_has_graph():
            return {"nodes": [], "links": []}
        db = get_db_manager()
        # 获取实体节点
        nodes = db.graph.query(f"""
            MATCH (e:`__Entity__`)
            RETURN e.id AS id, e.description AS description,
                   labels(e) AS labels
            LIMIT {limit}
        """)
        # 获取关系
        rels = db.graph.query(f"""
            MATCH (e1:`__Entity__`)-[r]->(e2:`__Entity__`)
            RETURN e1.id AS source, e2.id AS target,
                   type(r) AS rel_type, r.description AS description,
                   r.weight AS weight
            LIMIT {limit}
        """)

        # 组装节点列表
        node_list = []
        node_ids = set()
        for n in nodes:
            node_id = n["id"]
            node_ids.add(node_id)
            type_label = "Entity"
            if n.get("labels"):
                type_label = next((l for l in n["labels"] if l != "__Entity__"), "Entity")
            node_list.append({
                "id": node_id,
                "label": node_id,
                "group": type_label,
                "description": n.get("description", "") or "",
            })

        # 只保留两端节点都在已返回节点列表中的关系，避免前端报错
        link_list = []
        for r in rels:
            if r["source"] not in node_ids or r["target"] not in node_ids:
                continue
            w = float(r.get("weight", 1) or 1)
            link_list.append({
                "source": r["source"],
                "target": r["target"],
                "label": r.get("rel_type", ""),
                "weight": w,
                "description": r.get("description", "") or "",
            })

        return {"nodes": node_list, "links": link_list}
    except Exception as e:
        return {"nodes": [], "links": [], "error": str(e)}



# ===== 知识图谱构建接口 =====

PIPELINE_STAGES = [
    {"id": "build_graph", "label": "1. 构建图结构"},
    {"id": "build_index", "label": "2. 实体索引与社区"},
    {"id": "build_chunk_index", "label": "3. Chunk 索引"},
]


@st.cache_resource(ttl=30)
def check_neo4j() -> tuple:
    """检查 Neo4j 连接状态"""
    try:
        db = get_db_manager()
        db.graph.query("RETURN 1 AS ok")
        return True, f"Neo4j 已连接 ({db.neo4j_uri})"
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=60, show_spinner=False)
def get_graph_stats() -> dict:
    """获取知识图谱统计"""
    try:
        if not check_has_graph():
            return {"connected": True, "entities": 0, "total_relations": 0, "communities": 0, "chunks": 0}
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


def get_library_stats() -> dict:
    """获取知识库文档/Chunk 统计"""
    try:
        if not check_has_graph():
            return {"documents": 0, "chunks": 0, "vector_dim": 0}
        db = get_db_manager()
        r = db.graph.query("""
            MATCH (d:__Document__) WITH count(d) AS documents
            OPTIONAL MATCH (c:__Chunk__) RETURN documents, count(c) AS chunks
        """)
        row = r[0] if r else {}
        return {"documents": row.get("documents", 0), "chunks": row.get("chunks", 0), "vector_dim": 0}
    except Exception:
        return {"documents": 0, "chunks": 0, "vector_dim": 0}


def list_docs() -> list:
    """列出已入库文档"""
    import os
    try:
        if not check_has_graph():
            return []
        db = get_db_manager()
        result = db.graph.query("MATCH (d:__Document__) RETURN d.fileName AS file_name")
        return [{"title": os.path.basename(r["file_name"]), "source_file": r["file_name"]} for r in result]
    except Exception:
        return []


# 全局单例，避免每次点击都重新初始化
_processor = None


def _get_processor():
    global _processor
    if _processor is None:
        from backend.integrations.main import KnowledgeGraphProcessor
        _processor = KnowledgeGraphProcessor()
    return _processor


@st.cache_data(ttl=30, show_spinner=False)
def check_has_graph() -> bool:
    """检查知识图谱是否已构建（轻量，不触发处理器初始化）"""
    try:
        r = get_db_manager().graph.query("MATCH (n) RETURN count(n) AS total")
        return bool(r and r[0].get("total", 0) > 0)
    except Exception:
        return False


def update_graph() -> dict:
    """更新图谱（Embedding、社区检测等，不检测文件变更）"""
    try:
        _get_processor().update_graph()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_pipeline(
    file_paths: list[str] = None,
    directory_path: str = None,
    on_status=None,
    on_log=None,
    on_step_start=None,
    on_step_end=None,
    incremental: bool = False,
) -> dict:
    """分步执行知识图谱构建，并通过回调汇报进度"""
    if on_log:
        on_log("[INFO] 开始知识图谱构建流程...")
    if on_status:
        on_status("初始化...", 0.0)

    try:
        from backend.graph.core import connection_manager
        from frontend.utils.log_bridge import bridge_pipeline_logs

        processor = _get_processor()

        with bridge_pipeline_logs(processor, on_log):
            if incremental:
                if on_step_start:
                    on_step_start("graph", "增量更新：检测变更文件...", 0.15)
                processor.process_all(
                    file_paths=file_paths,
                    directory_path=directory_path,
                    incremental=True,
                )
                if on_step_end:
                    on_step_end("clear", True, skipped=True)
                    for sid in ("graph", "index", "chunk"):
                        on_step_end(sid, True)
            else:
                if on_step_start:
                    on_step_start("clear", "步骤 1/4：清除旧索引...", 0.08)
                connection_manager.drop_all_indexes()
                if on_step_end:
                    on_step_end("clear", True)

                if on_step_start:
                    on_step_start("graph", "步骤 2/4：构建图结构...", 0.25)
                result = processor.graph_builder.process(
                    file_paths=file_paths, directory_path=directory_path,
                )
                if on_step_end:
                    on_step_end("graph", bool(result))

                if result:
                    if on_step_start:
                        on_step_start("index", "步骤 3/4：实体索引与社区...", 0.55)
                    processor.index_community_builder.process()
                    if on_step_end:
                        on_step_end("index", True)

                    if on_step_start:
                        on_step_start("chunk", "步骤 4/4：Chunk 索引...", 0.82)
                    processor.chunk_index_builder.process()
                    if on_step_end:
                        on_step_end("chunk", True)
                else:
                    for sid in ("index", "chunk"):
                        if on_step_end:
                            on_step_end(sid, True, skipped=True)

        stats = get_graph_stats()
        if on_log:
            on_log(f"[DONE] 构建完成 — 实体 {stats.get('entities', 0)}，关系 {stats.get('total_relations', 0)}")
        if on_status:
            on_status("构建完成", 1.0)
        return {
            "success": True,
            "stats": stats,
            "stage_results": {"build_graph": True, "build_index": True, "build_chunk_index": True},
        }
    except Exception as e:
        if on_log:
            on_log(f"[ERROR] 构建失败: {e}")
        if on_status:
            on_status("构建失败", 1.0)
        cur = st.session_state.get("kg_pipeline_current")
        if cur and on_step_end:
            on_step_end(cur, False)
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
