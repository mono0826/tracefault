"""Streamlit 应用主入口

三页导航：智能问答、知识管理、管理后台
"""

import os
import sys
from pathlib import Path

# Windows SSL 证书修复
_ca = Path(r"G:\system1_software\anaconda\Library\ssl\cacert.pem")
if _ca.exists():
    os.environ.setdefault("SSL_CERT_FILE", str(_ca))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_ca))

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from frontend.utils.performance import init_performance_monitoring
from frontend.components.styles import custom_css
from frontend.common.session import init_session_state

st.set_page_config(
    page_title="设备故障智能诊断",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== 导航 =====
pg = st.navigation([
    st.Page("pages/chat.py", title="故障诊断", icon="🔧"),
    st.Page("pages/knowledge.py", title="知识库", icon="📚"),
    st.Page("pages/admin.py", title="管理后台", icon="🔐"),
])

# 全局初始化
init_session_state()
init_performance_monitoring()
custom_css()

pg.run()
