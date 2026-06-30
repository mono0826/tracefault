"""顶栏系统状态指示"""

import streamlit as st

from frontend.utils.api_client import check_neo4j, get_graph_stats, get_library_stats


def get_system_stats() -> dict:
    """获取顶栏展示用的系统统计"""
    neo4j_ok, neo4j_msg = check_neo4j()
    lib = get_library_stats()
    graph = get_graph_stats() if neo4j_ok else {}
    return {
        "neo4j_ok": neo4j_ok,
        "neo4j_msg": neo4j_msg,
        "documents": lib.get("documents", 0),
        "entities": graph.get("entities", 0) if graph.get("connected") else 0,
        "relations": graph.get("total_relations", 0) if graph.get("connected") else 0,
    }


def render_status_pills(stats: dict = None) -> str:
    """生成右侧状态胶囊 HTML（单行，避免 Streamlit 解析断行）"""
    if stats is None:
        stats = get_system_stats()
    dot = "status-dot-ok" if stats["neo4j_ok"] else "status-dot-error"
    neo4j_text = "Neo4j 已连接" if stats["neo4j_ok"] else "Neo4j 未连接"
    return (
        f'<div class="toolbar-pills">'
        f'<span class="toolbar-pill"><span class="status-dot {dot}"></span>{neo4j_text}</span>'
        f'<span class="toolbar-pill">文档 {stats["documents"]}</span>'
        f'<span class="toolbar-pill">实体 {stats["entities"]}</span>'
        f'<span class="toolbar-pill">关系 {stats["relations"]}</span>'
        f'</div>'
    )


def display_status_bar():
    """兼容旧调用 — 仅渲染状态胶囊行"""
    st.markdown(render_status_pills(), unsafe_allow_html=True)
