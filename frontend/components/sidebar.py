"""侧边栏 — 精简版：品牌 + 新对话 + 当前会话"""

import streamlit as st

from frontend.utils.api_client import clear_chat


def _get_chat_title() -> str:
    for msg in st.session_state.get("messages", []):
        if msg["role"] == "user":
            text = msg["content"].strip()
            return text[:16] + ("…" if len(text) > 16 else "")
    return "新对话"


def display_sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div class="ind-brand">
                <div class="ind-brand-icon">⚙</div>
                <div class="ind-brand-text">
                    <div class="ind-brand-name">故障诊断系统</div>
                    <div class="ind-brand-tag">Equipment Fault QA</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="ind-new-chat">', unsafe_allow_html=True)
        if st.button("＋  新对话", width="stretch", key="sidebar_new_chat"):
            clear_chat()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="ind-section-label">当前会话</div>', unsafe_allow_html=True)
        st.markdown('<div class="ind-history-active">', unsafe_allow_html=True)
        st.button(f"💬  {_get_chat_title()}", width="stretch", disabled=True, key="sidebar_current_chat")
        st.markdown("</div>", unsafe_allow_html=True)
