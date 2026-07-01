"""知识管理页面 — 图谱构建 + 图谱可视化"""

import sys
from pathlib import Path

import streamlit as st

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

st.session_state["_active_nav_key"] = "nav_knowledge"

from frontend.utils.api_client import (
    check_neo4j, check_has_graph, get_graph_stats, get_graph_data, update_graph,
)
from frontend.components.graph_view import (
    visualize_graph, render_display_settings, KG_VIS_PANEL_HEIGHT,
)
from frontend.components.layout import (
    subpage_header, metrics_row, section_header, empty_state, info_banner,
)
from frontend.components.pipeline_view import init_pipeline_state, _format_terminal_html
from frontend.utils.native_dialog import pick_folder, pick_files
from frontend.utils.helpers import count_folder_files
from frontend.common.base import run_pipeline_ui


subpage_header("📚", "知识库管理", "构建与可视化 Neo4j 知识图谱")

tab_graph, tab_visual = st.tabs(["🕸️ 图谱构建", "👁️ 图谱可视化"])

# ========== 知识图谱构建 Tab ==========
with tab_graph:
    init_pipeline_state()
    neo4j_ok, neo4j_msg = check_neo4j()

    gstats = get_graph_stats() if neo4j_ok else {}
    if gstats.get("connected"):
        metrics_row([
            ("🏷️", "实体数", gstats.get("entities", 0)),
            ("🔗", "关系数", gstats.get("total_relations", 0)),
            ("📦", "Chunk 数", gstats.get("chunks", 0)),
            ("👥", "社区数", gstats.get("communities", 0)),
        ], columns=4)
    else:
        metrics_row([
            ("🏷️", "实体数", "-"),
            ("🔗", "关系数", "-"),
            ("📦", "Chunk 数", "-"),
            ("👥", "社区数", "-"),
        ], columns=4)

    # --- 构建控制台（输入 / 模式 / 执行 三栏）---
    with st.container(border=True):
        section_header("🚀 构建控制台", "选择输入来源与构建模式，点击开始构建")

        doc_files, dir_path = [], None

        col_input, col_mode, col_action = st.columns([5, 4, 2], gap="medium")

        with col_input:
            st.markdown('<p class="build-panel-label">① 输入来源</p>', unsafe_allow_html=True)
            input_mode = st.radio(
                "输入类型",
                [("文件夹", "dir"), ("文件", "files")],
                format_func=lambda x: x[0],
                horizontal=True,
                label_visibility="collapsed",
                key="kg_input_mode",
            )

            if input_mode[1] == "dir":
                st.session_state.setdefault("kg_selected_folder", "")
                if st.button(
                    "选择文件夹",
                    icon=":material/folder_open:",
                    width="stretch",
                    key="kg_pick_folder",
                ):
                    try:
                        folder = pick_folder()
                        if folder:
                            st.session_state.kg_selected_folder = folder
                            st.rerun()
                    except RuntimeError as e:
                        st.error(str(e))
                if st.session_state.kg_selected_folder:
                    input_path = Path(st.session_state.kg_selected_folder)
                    if input_path.is_dir():
                        dir_path = str(input_path)
                        file_count = count_folder_files(input_path)
                        st.markdown(
                            f'<p class="build-panel-hint">{input_path.name} · 共 {file_count} 个文件</p>',
                            unsafe_allow_html=True,
                        )
            else:
                st.session_state.setdefault("kg_selected_files", [])
                if st.button(
                    "选择文件",
                    icon=":material/description:",
                    width="stretch",
                    key="kg_pick_files",
                ):
                    try:
                        files = pick_files()
                        if files:
                            st.session_state.kg_selected_files = files
                            st.rerun()
                    except RuntimeError as e:
                        st.error(str(e))
                if st.session_state.kg_selected_files:
                    valid = [p for p in st.session_state.kg_selected_files if Path(p).is_file()]
                    if valid:
                        doc_files = [str(Path(p).resolve()) for p in valid]
                        label = Path(valid[0]).name if len(valid) == 1 else f"{Path(valid[0]).name} 等 {len(valid)} 个"
                        st.markdown(
                            f'<p class="build-panel-hint">{label}</p>',
                            unsafe_allow_html=True,
                        )

        with col_mode:
            st.markdown('<p class="build-panel-label">② 构建模式</p>', unsafe_allow_html=True)
            mode = st.radio(
                "构建模式",
                [("全量构建", "full"), ("增量更新", "incremental")],
                format_func=lambda x: x[0],
                captions=["清除旧数据，完整重建", "仅处理新增/变更文件"],
                label_visibility="collapsed",
                key="kg_build_mode",
            )

        with col_action:
            st.markdown('<p class="build-panel-label">③ 执行</p>', unsafe_allow_html=True)
            has_input = bool(dir_path) or bool(doc_files)
            can_build = neo4j_ok and has_input
            if st.button(
                "开始构建",
                type="primary",
                icon=":material/rocket_launch:",
                width="stretch",
                disabled=not can_build,
                key="kg_start_build",
            ):
                st.session_state.kg_run_params = {
                    "input_mode": input_mode[1],
                    "dir_path": dir_path,
                    "doc_files": doc_files,
                    "incremental": mode[1] == "incremental",
                }
                st.rerun()
            if not neo4j_ok:
                st.caption("⚠️ Neo4j 未连接")
            elif not has_input:
                st.caption("请先选择输入源")

    # --- 构建终端（全宽）---
    section_header("📟 构建终端", "实时显示构建日志与当前执行步骤")
    if not neo4j_ok:
        info_banner(f"⚠️ {neo4j_msg}", "warning")
        info_banner("知识图谱构建需要 Neo4j。请运行 <code>docker-compose up -d</code> 启动。", "info")
    terminal_ph = st.empty()
    terminal_ph.markdown(
        _format_terminal_html(
            st.session_state.get("kg_pipeline_logs", []),
            st.session_state.get("kg_pipeline_status", "就绪 — 选择输入源后点击「开始构建」"),
        ),
        unsafe_allow_html=True,
    )
    progress_ph = st.empty()

    run_params = st.session_state.pop("kg_run_params", None)
    if run_params:
        is_inc = run_params["incremental"]
        if run_params["input_mode"] == "dir":
            run_pipeline_ui(
                directory_path=run_params["dir_path"],
                incremental=is_inc,
                terminal_placeholder=terminal_ph,
                progress_placeholder=progress_ph,
            )
        else:
            run_pipeline_ui(
                document_paths=run_params["doc_files"],
                incremental=is_inc,
                terminal_placeholder=terminal_ph,
                progress_placeholder=progress_ph,
            )

# ========== 图谱可视化 Tab ==========
with tab_visual:
    section_header("👁️ 知识图谱可视化", "展示 Neo4j 中的实体和关系网络")

    neo4j_ok, neo4j_msg = check_neo4j()
    if not neo4j_ok:
        info_banner(f"Neo4j 不可用: {neo4j_msg}", "warning")
    elif not check_has_graph():
        empty_state("🕸️", "图谱尚未构建", "请先在「图谱构建」Tab 中构建知识图谱")
    else:
        ctrl_col, graph_col = st.columns([1, 4])

        with ctrl_col:
            with st.container(border=True, height=KG_VIS_PANEL_HEIGHT):
                gstats = get_graph_stats()
                if gstats.get("connected"):
                    section_header("图谱统计")
                    metrics_row([
                        ("🏷️", "实体", gstats.get("entities", 0)),
                        ("🔗", "关系", gstats.get("total_relations", 0)),
                    ], columns=2)

                st.markdown("---")
                section_header("控制面板")
                limit = st.number_input("节点上限", min_value=50, max_value=500, value=200, step=50)
                refresh = st.button("🔄 刷新图谱", type="primary", width="stretch")

                st.markdown("---")
                render_display_settings()

        if "kg_cache" not in st.session_state:
            st.session_state.kg_cache = None

        if refresh:
            with graph_col:
                with st.spinner("正在更新 Embedding 与社区检测..."):
                    update_graph()
            st.session_state.kg_cache = None
            st.rerun()

        kg_data = st.session_state.kg_cache
        if kg_data is None:
            with graph_col:
                with st.spinner("加载图谱数据..."):
                    kg_data = get_graph_data(limit=limit)
                    st.session_state.kg_cache = kg_data

        with graph_col:
            if kg_data and kg_data.get("nodes"):
                with st.container(border=True, height=KG_VIS_PANEL_HEIGHT):
                    st.caption(f"当前显示 {len(kg_data['nodes'])} 个节点 · {len(kg_data['links'])} 条关系")
                    visualize_graph(kg_data)
            elif kg_data:
                with st.container(border=True, height=KG_VIS_PANEL_HEIGHT):
                    empty_state("📊", "图谱暂无数据", "请先在「图谱构建」中构建知识图谱")
