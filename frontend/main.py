"""Streamlit 应用主入口

三页导航：智能问答（增强版）、知识管理、管理后台
"""

import os
import sys
from pathlib import Path

# Windows SSL 证书修复：使用 conda 自带的 cacert.pem 而非 Windows 证书存储
# 解决 ssl.SSLError: [ASN1: NOT_ENOUGH_DATA]
_ca = Path(r"G:\system1_software\anaconda\Library\ssl\cacert.pem")
if _ca.exists():
    os.environ.setdefault("SSL_CERT_FILE", str(_ca))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_ca))

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from frontend.utils.helpers import generate_session_id
from frontend.utils.performance import init_performance_monitoring
from frontend.components.styles import custom_css
from frontend.components.sidebar import display_sidebar
from frontend.components.chat import display_chat_interface
from frontend.components.debug import display_debug_panel


st.set_page_config(
    page_title="设备故障智能问答",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_session_state():
    """初始化所有会话状态变量"""
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


def chat_page():
    """智能问答页面（增强版）"""
    _init_session_state()

    # 侧边栏
    display_sidebar()

    # 主区域
    if st.session_state.debug_mode:
        # 调试模式：左右分栏
        col1, col2 = st.columns([5, 4])
        with col1:
            display_chat_interface()
        with col2:
            display_debug_panel()
    else:
        display_chat_interface()


# ===== 导航 =====
pg = st.navigation([
    st.Page(chat_page, title="智能问答", icon="💬"),
    st.Page("pages/knowledge.py", title="知识管理", icon="📚"),
    st.Page("pages/admin.py", title="管理后台", icon="🔐"),
])

# 全局初始化
_init_session_state()
init_performance_monitoring()
custom_css()

pg.run()
