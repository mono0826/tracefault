"""可复用的聊天消息组件"""

import streamlit as st


def render_message(role: str, content: str, sources: list[str] | None = None):
    """渲染单条对话消息"""
    avatar = "🧑‍💼" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)
        if sources:
            with st.expander("📎 参考来源"):
                for src in sources:
                    st.markdown(f"- {src}")


def render_feedback_buttons(msg_index: int):
    """渲染有用/无用反馈按钮"""
    col1, col2 = st.columns([1, 20])
    with col1:
        if st.button("👍", key=f"up_{msg_index}"):
            st.toast("感谢反馈！")
    with col2:
        if st.button("👎", key=f"down_{msg_index}"):
            st.toast("已记录，我们将持续优化。")
