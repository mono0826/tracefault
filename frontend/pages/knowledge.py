"""知识管理页面 — 上传文档并处理到知识库"""

import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.knowledge_base import (
    process_and_store_document,
    get_knowledge_stats,
    list_documents,
)
from backend.config.settings import PROJECT_ROOT

DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

st.title("📚 知识库管理")
st.caption("上传设备手册、故障案例等技术文档，自动解析并存入知识库")

# ---------- 上传文档 ----------
with st.expander("📤 上传文档", expanded=True):
    uploaded_files = st.file_uploader(
        "选择文档（PDF / Word / Markdown / TXT，可多选）",
        type=["pdf", "docx", "md", "txt"],
        accept_multiple_files=True,
        key="doc_uploader",
    )

    if uploaded_files:
        # 记录已处理的文件名，防止重复
        processed_key = "processed_files"
        if processed_key not in st.session_state:
            st.session_state[processed_key] = set()

        new_files = [f for f in uploaded_files if f.name not in st.session_state[processed_key]]

        if new_files:
            # 保存所有新文件
            for f in new_files:
                (DOCUMENTS_DIR / f.name).write_bytes(f.getbuffer())

            st.info(f"已保存 {len(new_files)} 个文件，正在解析...")

            # 逐个处理
            progress = st.progress(0, text="处理中...")
            for i, f in enumerate(new_files):
                progress.progress((i + 1) / len(new_files), text=f"处理: {f.name}")
                result = process_and_store_document(str(DOCUMENTS_DIR / f.name))
                st.session_state[processed_key].add(f.name)
                if result["status"] == "success":
                    st.success(f"✅ {f.name} — {result['chunk_count']} 个 Chunk")
                else:
                    st.error(f"❌ {f.name} — {result['message']}")

if st.button("🔄 刷新统计"):
    st.rerun()

# ---------- 知识库统计 ----------
stats = get_knowledge_stats()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📄 文档数", stats["documents"])
with col2:
    st.metric("🧩 Chunk 数", stats["chunks"])
with col3:
    st.metric("📐 向量维度", stats["vector_dim"] or "-")

# ---------- 知识列表 ----------
st.subheader("已处理文档")

docs = list_documents()
if docs:
    df = pd.DataFrame(docs)
    # 重命名列
    df.columns = ["标题", "源文件"]
    st.dataframe(df, width="stretch", hide_index=True)
else:
    st.info("知识库为空，请上传文档")
