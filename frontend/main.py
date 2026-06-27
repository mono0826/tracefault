"""Streamlit 应用主入口"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，以便导入 backend 包
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from frontend.utils.helpers import generate_session_id

st.set_page_config(
    page_title="设备故障智能问答",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """初始化会话状态"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = generate_session_id()
    if "messages" not in st.session_state:
        st.session_state.messages = []


def chat_page():
    """智能问答页面"""
    init_session_state()

    st.title("🔧 企业设备故障智能问答系统")
    st.caption("基于知识库的智能诊断助手 — 输入设备故障描述，获取诊断建议")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("描述设备故障现象..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("正在分析故障..."):
                # TODO: 调用 backend.agent.graph
                answer = "收到您的问题。智能问答功能将在后续版本中实现。"
                st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


# ---------- 导航 ----------
pg = st.navigation([
    st.Page(chat_page, title="智能问答", icon="💬"),
    st.Page("pages/knowledge.py", title="知识管理", icon="📚"),
    st.Page("pages/admin.py", title="管理后台", icon="🔐"),
])
pg.run()
