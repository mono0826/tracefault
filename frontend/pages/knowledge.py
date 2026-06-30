"""知识管理页面 — 上传文档处理到知识库 + 构建知识图谱"""

import os
import sys
from pathlib import Path

import streamlit as st
import pandas as pd

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.pipelines.document_processor import DocumentProcessor
from backend.integrations.main import KnowledgeGraphProcessor
from backend.config.settings import UPLOAD_FILES_DIR
from backend.config.neo4jdb import get_db_manager

from frontend.utils.api_client import (
    run_pipeline,
    run_fast_pipeline,
    check_neo4j,
    check_has_graph,
    get_graph_stats,
    get_graph_data,
    update_graph,
    PIPELINE_STAGES,
)
from frontend.components.graph_view import visualize_graph

UPLOAD_FILES_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================
#  图构建 UI
# =============================================================

_LABEL_MAP = {s["id"]: s["label"] for s in PIPELINE_STAGES}


def _render_stage_table(stage_results: dict):
    """以表格展示管道各阶段结果"""
    if not stage_results:
        return
    rows = []
    for sid, ok in stage_results.items():
        icon = "✅" if ok else "❌"
        rows.append({"阶段": _LABEL_MAP.get(sid, sid), "状态": f"{icon} {'完成' if ok else '失败'}"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _run_pipeline_ui(document_paths: list[str] = None, directory_path: str = None, incremental: bool = False):
    """执行管道并在 UI 逐步显示进度"""
    neo4j_ok, neo4j_msg = check_neo4j()
    if not neo4j_ok:
        st.error(f"Neo4j 不可用: {neo4j_msg}")
        return

    progress_bar = st.progress(0, text="准备就绪...")
    status_text = st.empty()
    log_area = st.container()
    stage_area = st.container()

    logs = []

    def _on_status(msg: str, pct: float):
        status_text.info(msg)
        progress_bar.progress(min(pct, 1.0), text=msg)

    def _on_log(msg: str):
        logs.append(msg)
        with log_area:
            st.code("\n".join(logs[-20:]), language="text")

    st.info("开始构建知识图谱，请耐心等待...")

    result = run_pipeline(
        file_paths=document_paths,
        directory_path=directory_path,
        on_status=_on_status,
        on_log=_on_log,
        incremental=incremental,
    )

    status_text.success("管道执行完成" if result["success"] else "管道执行完成，部分阶段有异常")
    progress_bar.progress(1.0, text="完成")

    with stage_area:
        st.subheader("执行结果")
        _render_stage_table(result.get("stage_results", {}))

    # 图统计
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


def _process_document(file_path: str) -> dict:
    """处理单个文档"""
    import os
    processor = DocumentProcessor()
    file_chunks = processor.process(file_paths=file_path)
    if not file_chunks:
        return {"status": "failed", "message": "处理失败", "chunk_count": 0}
    _, chunks = file_chunks[0]
    return {"status": "success", "filename": os.path.basename(file_path), "chunk_count": len(chunks)}


def _get_stats() -> dict:
    """获取知识库统计"""
    try:
        db = get_db_manager()
        r = db.graph.query("""
            MATCH (d:__Document__) WITH count(d) AS documents
            OPTIONAL MATCH (c:__Chunk__) RETURN documents, count(c) AS chunks
        """)
        row = r[0] if r else {}
        return {"documents": row.get("documents", 0), "chunks": row.get("chunks", 0), "vector_dim": 0}
    except Exception:
        return {"documents": 0, "chunks": 0, "vector_dim": 0}


def _list_docs() -> list:
    """列出文档"""
    try:
        db = get_db_manager()
        result = db.graph.query("MATCH (d:__Document__) RETURN d.fileName AS file_name")
        return [{"title": os.path.basename(r["file_name"]), "source_file": r["file_name"]} for r in result]
    except Exception:
        return []


# =============================================================
#  主页面
# =============================================================

st.title("📚 知识库管理")
st.caption("上传设备手册、故障案例等技术文档，自动解析并存入知识库")

tab_docs, tab_graph, tab_visual = st.tabs(["📄 文档管理", "🕸️ 知识图谱构建", "👁️ 图谱可视化"])

# ========== 文档管理 Tab ==========
with tab_docs:
    with st.expander("📤 上传文档", expanded=True):
        uploaded_files = st.file_uploader(
            "选择文档（PDF / Word / Markdown / TXT，可多选）",
            type=["pdf", "docx", "md", "txt"],
            accept_multiple_files=True,
            key="doc_uploader",
        )

        if uploaded_files:
            processed_key = "processed_files"
            if processed_key not in st.session_state:
                st.session_state[processed_key] = set()

            new_files = [f for f in uploaded_files if f.name not in st.session_state[processed_key]]

            if new_files:
                doc_paths = []
                for f in new_files:
                    save_path = UPLOAD_FILES_DIR / f.name
                    save_path.write_bytes(f.getbuffer())
                    doc_paths.append(str(save_path))
                    st.session_state[processed_key].add(f.name)

                st.info(f"已上传 {len(new_files)} 个文件，增量构建知识图谱...")
                _run_pipeline_ui(
                    document_paths=doc_paths, 
                    incremental=True
                )
                st.rerun()

        if st.button("🔄 刷新统计"):
            st.rerun()

    stats = _get_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("📄 文档数", stats["documents"])
    col2.metric("🧩 Chunk 数", stats["chunks"])
    col3.metric("📐 向量维度", stats["vector_dim"] or "-")

    st.subheader("已处理文档")
    docs = _list_docs()
    if docs:
        df = pd.DataFrame(docs)
        df.columns = ["标题", "源文件"]
        df.insert(0, "序号", range(1, len(df) + 1))
        st.dataframe(df, hide_index=True,
                     column_config={"序号": st.column_config.NumberColumn(width="small")})
    else:
        st.info("知识库为空，请上传文档")

# ========== 知识图谱构建 Tab ==========
with tab_graph:
    st.subheader("🕸️ 知识图谱构建管道")
    st.markdown("""
    基于已上传文档，在 Neo4j 中构建知识图谱。完整流程：

    | 步骤 | 说明 |
    |------|------|
    | 1. 构建图结构 | 创建 Document / Chunk 节点与关系 |
    | 2. 提取实体关系 | LLM 从文档中提取实体和关系 |
    | 3. 写入图数据库 | 将实体关系写入 Neo4j |
    | 4. 向量索引 | 为 Chunk 和 Entity 创建向量索引 |
    | 5. 实体处理 | 相似检测 → 合并 → 消歧 → 对齐 |
    | 6. 社区检测 | Leiden 算法发现社区结构 |
    | 7. 社区摘要 | LLM 生成社区摘要 |
    """)

    neo4j_ok, neo4j_msg = check_neo4j()
    if neo4j_ok:
        st.success(f"✅ {neo4j_msg}")
    else:
        st.warning(f"⚠️ {neo4j_msg}")
        st.info("知识图谱构建需要 Neo4j。请运行 `docker-compose up -d` 启动 Neo4j。")

    if neo4j_ok:
        stats = get_graph_stats()
        if stats.get("connected"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏷️ 实体", stats.get("entities", 0))
            c2.metric("🔗 关系", stats.get("total_relations", 0))
            c3.metric("📦 Chunk", stats.get("chunks", 0))
            c4.metric("👥 社区", stats.get("communities", 0))

    st.markdown("---")

    st.subheader("选择输入源")
    input_mode = st.radio(
        "输入类型",
        [("📁 文件夹路径", "dir"), ("📄 文件上传", "files")],
        format_func=lambda x: x[0],
        horizontal=True,
    )

    doc_files = []
    dir_path = None

    if input_mode[1] == "dir":
        # 系统文件夹选择对话框
        if "kg_selected_folder" not in st.session_state:
            st.session_state.kg_selected_folder = ""

        col_btn, col_path = st.columns([1, 3])
        with col_btn:
            if st.button("📂 选择文件夹", use_container_width=True):
                try:
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes("-topmost", True)
                    folder = filedialog.askdirectory()
                    root.destroy()
                    if folder:
                        st.session_state.kg_selected_folder = folder
                        st.rerun()
                except Exception as e:
                    st.error(f"打开文件夹对话框失败: {e}")

        with col_path:
            folder_path = st.text_input(
                "已选择路径",
                value=st.session_state.kg_selected_folder,
                placeholder="点击左侧按钮选择文件夹",
                label_visibility="collapsed",
            )

        if st.session_state.kg_selected_folder:
            input_path = Path(st.session_state.kg_selected_folder)
            if input_path.exists() and input_path.is_dir():
                dir_path = str(input_path)
                doc_count = len(list(input_path.rglob("*")))
                st.caption(f"已选择: {input_path}")

    else:  # file upload mode
        uploaded_files = st.file_uploader(
            "选择文档文件（可多选）",
            type=["pdf", "docx", "md", "txt"],
            accept_multiple_files=True,
            key="graph_doc_uploader",
        )
        if uploaded_files:
            print(f"uploaded_files = {uploaded_files}")
            for f in uploaded_files:
                save_path = UPLOAD_FILES_DIR / f.name
                save_path.write_bytes(f.getbuffer())
                doc_files.append(str(save_path))
            st.caption(f"已选择 {len(doc_files)} 个文件")

    col_mode, col_btn = st.columns([3, 1])
    with col_mode:
        mode = st.radio(
            "构建模式",
            [("全量构建（清除旧数据重建）", "full"), ("增量更新（只处理变更文件）", "incremental")],
            format_func=lambda x: x[0],
            index=0,
            help="全量：清空所有旧数据重新构建 | 增量：只处理新增和修改的文件，保留已有数据",
        )

    has_input = bool(dir_path) or bool(doc_files)
    if not has_input:
        st.info("请先选择文档输入源，然后点击「开始构建」。")
    else:
        with col_btn:
            mode_key = mode[1]
            is_inc = (mode_key == "incremental")
            if st.button("🚀 开始构建", type="primary", use_container_width=True):
                if input_mode[1] == "dir":
                    _run_pipeline_ui(directory_path=dir_path, incremental=is_inc)
                else:
                    _run_pipeline_ui(document_paths=doc_files, incremental=is_inc)

# ========== 图谱可视化 Tab ==========
with tab_visual:
    st.subheader("👁️ 知识图谱可视化")
    st.caption("展示 Neo4j 中的实体和关系网络图")

    neo4j_ok, neo4j_msg = check_neo4j()
    if not neo4j_ok:
        st.warning(f"⚠️ Neo4j 不可用: {neo4j_msg}")
    elif not check_has_graph():
        st.warning("⚠️ 知识图谱尚未构建，请先在「知识图谱构建」中构建图谱")
    else:
        col_left, col_right = st.columns([3, 1])
        with col_right:
            limit = st.number_input("节点数量上限", min_value=50, max_value=500, value=200, step=50)
            refresh = st.button("🔄 刷新图谱", type="primary", use_container_width=True)

        kg_data = None
        if "kg_cache" not in st.session_state:
            st.session_state.kg_cache = None

        if refresh:
            status_placeholder = st.empty()
            with status_placeholder.container():
                st.markdown("<div style='text-align:center;padding:80px 0'><h3>🔄 更新图谱中...</h3><p>正在更新 Embedding 与社区检测</p></div>", unsafe_allow_html=True)
                update_graph()
            status_placeholder.empty()
            st.session_state.kg_cache = None

        if st.session_state.kg_cache is None:
            with col_left:
                with st.spinner("加载图谱数据..."):
                    kg_data = get_graph_data(limit=limit)
                    st.session_state.kg_cache = kg_data
        else:
            kg_data = st.session_state.kg_cache

        if kg_data:
            stats = get_graph_stats()
            if stats.get("connected"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🏷️ 实体", stats.get("entities", 0))
                c2.metric("🔗 关系", stats.get("total_relations", 0))
                c3.metric("📦 Chunk", stats.get("chunks", 0))
                c4.metric("👥 社区", stats.get("communities", 0))

            if kg_data.get("nodes"):
                st.caption(f"当前显示 {len(kg_data['nodes'])} 个节点, {len(kg_data['links'])} 条关系")
                visualize_graph(kg_data)
            else:
                st.info("图谱中暂无数据，请先在「知识图谱构建」中构建图谱")
