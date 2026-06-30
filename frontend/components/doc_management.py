"""知识库文档管理 — 已处理文档列表"""

import streamlit as st

from frontend.common.base import list_docs
from frontend.components.layout import section_header, empty_state, render_doc_table


def render_document_management():
    """文档管理区块：标题 + 表格（表格起始位置与设备列表页 placeholder-hint 齐平）"""
    head_col, refresh_col = st.columns([9, 1], vertical_alignment="center")
    with head_col:
        section_header("已处理文档", "查看已入库文档列表，导入与构建请前往「知识库 → 图谱构建」")
    with refresh_col:
        if st.button("🔄 刷新", type="secondary", key="doc_mgmt_refresh", width="stretch"):
            st.rerun()

    docs = list_docs()
    if docs:
        render_doc_table(docs)
    else:
        empty_state("📭", "知识库为空", "请先在「知识库 → 图谱构建」中导入并构建文档")
