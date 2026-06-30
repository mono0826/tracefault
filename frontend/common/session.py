"""全局 Session State 初始化"""

import streamlit as st

from frontend.utils.helpers import generate_session_id


def init_session_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = generate_session_id()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "execution_log" not in st.session_state:
        st.session_state.execution_log = []
    if "source_content" not in st.session_state:
        st.session_state.source_content = None
    if "agent_type" not in st.session_state:
        st.session_state.agent_type = "naive_rag_agent"
    if "show_thinking" not in st.session_state:
        st.session_state.show_thinking = False
    if "use_deeper_tool" not in st.session_state:
        st.session_state.use_deeper_tool = True
    if "use_stream" not in st.session_state:
        st.session_state.use_stream = True
    if "processing_lock" not in st.session_state:
        st.session_state.processing_lock = False
    if "feedback_given" not in st.session_state:
        st.session_state.feedback_given = set()
    if "feedback_in_progress" not in st.session_state:
        st.session_state.feedback_in_progress = False
    if "performance_metrics" not in st.session_state:
        st.session_state.performance_metrics = []
    if "equipment_type" not in st.session_state:
        st.session_state.equipment_type = "未指定"
    if "equipment_id" not in st.session_state:
        st.session_state.equipment_id = ""
    if "fault_severity" not in st.session_state:
        st.session_state.fault_severity = "未指定"
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
