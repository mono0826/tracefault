"""跨页面共享工具函数"""

import sys
from pathlib import Path

import pandas as pd

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from frontend.utils.api_client import run_pipeline, check_neo4j, get_library_stats, list_docs, PIPELINE_STAGES
import streamlit as st

UPLOAD_FILES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
UPLOAD_FILES_DIR.mkdir(parents=True, exist_ok=True)

_LABEL_MAP = {s["id"]: s["label"] for s in PIPELINE_STAGES}


def render_stage_table(stage_results: dict):
    """以表格展示管道各阶段结果"""
    if not stage_results:
        return
    rows = []
    for sid, ok in stage_results.items():
        icon = "✅" if ok else "❌"
        rows.append({"阶段": _LABEL_MAP.get(sid, sid), "状态": f"{icon} {'完成' if ok else '失败'}"})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def run_pipeline_ui(
    document_paths: list[str] = None,
    directory_path: str = None,
    incremental: bool = False,
    steps_placeholder=None,
    terminal_placeholder=None,
    progress_placeholder=None,
):
    """执行管道 — 终端日志实时刷新"""
    from frontend.components.pipeline_view import (
        reset_pipeline_state,
        render_pipeline_progress,
        make_pipeline_callbacks,
        _format_terminal_html,
    )

    neo4j_ok, neo4j_msg = check_neo4j()
    if not neo4j_ok:
        st.error(f"Neo4j 不可用: {neo4j_msg}")
        return

    reset_pipeline_state()
    st.session_state.kg_pipeline_running = True
    if terminal_placeholder is None:
        st.markdown("---")
        terminal_placeholder = st.empty()

    terminal_placeholder.markdown(
        _format_terminal_html([], st.session_state.get("kg_pipeline_status", "正在启动..."), running=True),
        unsafe_allow_html=True,
    )

    progress_bar = (
        progress_placeholder.progress(0, text="准备就绪...")
        if progress_placeholder is not None
        else st.progress(0, text="准备就绪...")
    )
    logs: list[str] = []
    on_status, on_log, on_step_start, on_step_end = make_pipeline_callbacks(
        progress_bar, terminal_placeholder, logs, steps_placeholder,
    )

    result = {"success": False, "error": None, "stats": {}}
    try:
        result = run_pipeline(
            file_paths=document_paths,
            directory_path=directory_path,
            on_status=on_status,
            on_log=on_log,
            on_step_start=on_step_start,
            on_step_end=on_step_end,
            incremental=incremental,
        )
    finally:
        st.session_state.kg_pipeline_running = False

    final_msg = "构建完成" if result["success"] else "构建失败"
    st.session_state.kg_pipeline_status = final_msg
    progress_bar.progress(1.0, text=final_msg)
    if steps_placeholder is not None:
        with steps_placeholder.container():
            render_pipeline_progress()
    terminal_placeholder.markdown(
        _format_terminal_html(logs, final_msg, running=False),
        unsafe_allow_html=True,
    )

    stats = result.get("stats", {})
    if stats.get("connected"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏷️ 实体", stats.get("entities", 0))
        c2.metric("🔗 关系", stats.get("total_relations", 0))
        c3.metric("📦 Chunk", stats.get("chunks", 0))
        c4.metric("👥 社区", stats.get("communities", 0))
    if result.get("error"):
        st.error(f"管道异常: {result['error']}")
    st.rerun()


# get_library_stats / list_docs 见 frontend.utils.api_client
