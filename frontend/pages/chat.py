"""智能问答页面"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from frontend.common.session import init_session_state
from frontend.components.sidebar import display_sidebar
from frontend.components.chat import display_chat_interface
from frontend.components.debug import display_debug_panel


init_session_state()
st.session_state["_active_nav_key"] = "nav_chat"
display_sidebar()

if st.session_state.debug_mode:
    col1, col2 = st.columns([3, 2], gap="medium")
    with col1:
        display_chat_interface(show_summary_panel=False)
    with col2:
        display_debug_panel()
else:
    display_chat_interface()
