"""侧边栏 — 品牌 + 新对话 + 问答模式 + 历史记录"""

import streamlit as st

from frontend.common.constants import AGENT_OPTIONS, AGENT_DESCRIPTIONS
from frontend.utils.api_client import (
    clear_chat,
    list_chat_sessions,
    load_chat_session,
    delete_chat_session,
    start_new_chat_session,
)


def _apply_pending_agent_type():
    """历史会话加载后延迟写入 agent_type，避免与 radio widget 冲突"""
    pending = st.session_state.pop("_pending_agent_type", None)
    if pending is not None:
        st.session_state.agent_type = pending


def _css_content(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _render_agent_selector():
    if st.session_state.get("agent_type") not in AGENT_OPTIONS:
        st.session_state.agent_type = "general_agent"

    st.markdown('<div class="ind-section-label">问答模式</div>', unsafe_allow_html=True)
    tip_rules = []
    for idx, key in enumerate(AGENT_OPTIONS.keys(), start=1):
        desc = AGENT_DESCRIPTIONS.get(key, "")
        if desc:
            tip_rules.append(
                "section[data-testid=\"stSidebar\"] [data-testid=\"stRadio\"] > div > "
                f"label:nth-of-type({idx}) [data-testid=\"stMarkdownContainer\"] p::before "
                f'{{ content: "{_css_content(desc)}"; }}'
            )
    if tip_rules:
        st.markdown(f"<style>{''.join(tip_rules)}</style>", unsafe_allow_html=True)
    st.radio(
        "问答模式",
        options=list(AGENT_OPTIONS.keys()),
        format_func=lambda k: AGENT_OPTIONS[k],
        key="agent_type",
        label_visibility="collapsed",
    )


def _on_load_session(session_id: str):
    """on_click 回调结束后 Streamlit 会自动 rerun，勿在此调用 st.rerun()"""
    load_chat_session(session_id)


def _render_history_list():
    st.markdown('<div class="ind-section-label">历史记录</div>', unsafe_allow_html=True)
    sessions = list_chat_sessions()
    if not sessions:
        st.markdown('<p class="ind-history-empty">暂无历史会话</p>', unsafe_allow_html=True)
        return

    current_id = str(st.session_state.get("session_id", ""))
    row_css = []

    for sess in sessions:
        sid = str(sess["session_id"])
        title = sess.get("title", "新对话")
        time_label = sess.get("time_label", "")
        is_current = sid == current_id
        label = title if not time_label else f"{title}  ·  {time_label}"

        load_col, del_col = st.columns([6, 1], vertical_alignment="center")
        with load_col:
            if is_current:
                st.button(label, key=f"hist_load_{sid}", width="stretch", disabled=True)
            else:
                st.button(
                    label,
                    key=f"hist_load_{sid}",
                    width="stretch",
                    on_click=_on_load_session,
                    args=(sid,),
                )
            row_css.append(
                f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button {{"
                f"background:rgba(30,42,58,0.95)!important;background-color:rgba(30,42,58,0.95)!important;"
                f"border:1px solid rgba(255,255,255,0.1)!important;color:#94a3b8!important;"
                f"font-size:12px!important;text-align:left!important;box-shadow:none!important;"
                f"border-radius:6px!important;"
                f"transition:background 0.15s ease,border-color 0.15s ease,color 0.15s ease!important;"
                f"}}"
                f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button p {{"
                f"color:#94a3b8!important;"
                f"}}"
                f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button:hover:not(:disabled) {{"
                f"background:rgba(255,255,255,0.14)!important;background-color:rgba(255,255,255,0.14)!important;"
                f"border-color:rgba(255,255,255,0.22)!important;color:#f1f5f9!important;"
                f"cursor:pointer!important;"
                f"}}"
                f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button:hover:not(:disabled) p {{"
                f"color:#f1f5f9!important;"
                f"}}"
            )
            if is_current:
                row_css.append(
                    f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button:disabled {{"
                    f"opacity:1!important;color:#e2e8f0!important;"
                    f"border-color:rgba(255,255,255,0.18)!important;"
                    f"background:rgba(255,255,255,0.08)!important;"
                    f"background-color:rgba(255,255,255,0.08)!important;"
                    f"}}"
                    f"section[data-testid=\"stSidebar\"] .st-key-hist_load_{sid} button:disabled p {{"
                    f"color:#e2e8f0!important;"
                    f"}}"
                )
        with del_col:
            if st.button("×", key=f"hist_del_{sid}", help="删除"):
                delete_chat_session(sid)
                if sid == current_id:
                    start_new_chat_session()
                st.rerun()
            row_css.append(
                f"section[data-testid=\"stSidebar\"] .st-key-hist_del_{sid} button {{"
                f"background:transparent!important;background-color:transparent!important;"
                f"border:none!important;color:#64748b!important;"
                f"font-size:18px!important;box-shadow:none!important;border-radius:6px!important;"
                f"}}"
                f"section[data-testid=\"stSidebar\"] .st-key-hist_del_{sid} button:hover {{"
                f"background:#ef4444!important;background-color:#ef4444!important;"
                f"color:#ffffff!important;"
                f"}}"
                f"section[data-testid=\"stSidebar\"] .st-key-hist_del_{sid} button:hover p {{"
                f"color:#ffffff!important;"
                f"}}"
            )

    if row_css:
        st.markdown(f"<style>{''.join(row_css)}</style>", unsafe_allow_html=True)


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

        st.markdown('<div class="ind-history-active">', unsafe_allow_html=True)
        if st.button("💬  新对话", width="stretch", key="sidebar_new_chat"):
            clear_chat()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        _apply_pending_agent_type()
        _render_agent_selector()

        _render_history_list()
