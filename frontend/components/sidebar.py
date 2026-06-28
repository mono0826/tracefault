"""侧边栏 — Agent 选择、系统设置、示例问题"""

import streamlit as st

from frontend.utils.api_client import clear_chat

# 示例问题（与设备故障诊断相关）
EXAMPLE_QUESTIONS = [
    "设备运行中突然停机，可能的原因有哪些？",
    "如何排查电机过热故障？",
    "PLC 通讯中断怎么处理？",
    "液压系统压力不足，故障排查步骤",
    "变频器过流报警的常见原因",
]


def display_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🔧 设备故障诊断")
        st.markdown("---")

        # === Agent 选择 ===
        st.header("Agent 选择")

        agent_options = {
            "naive_rag_agent": "标准 RAG — 基础检索+生成",
            "deep_research_agent": "深度研究 — 多轮迭代搜索",
            "fusion_agent": "融合分析 — 多角度综合分析",
        }
        current = st.session_state.agent_type
        agent_keys = list(agent_options.keys())
        default_idx = agent_keys.index(current) if current in agent_keys else 0

        agent_type = st.radio(
            "选择检索策略:",
            options=agent_keys,
            format_func=lambda k: k.replace("_", " ").title(),
            index=default_idx,
            help="\n\n".join(f"**{k}**: {v}" for k, v in agent_options.items()),
            key="sidebar_agent_type",
        )
        if agent_type != st.session_state.agent_type:
            st.session_state.agent_type = agent_type

        # 深度研究专属选项
        if agent_type == "deep_research_agent":
            show_thinking = st.checkbox(
                "显示推理过程",
                value=st.session_state.get("show_thinking", False),
                key="sidebar_show_thinking",
                help="在回答前显示AI的思考和分析过程",
            )
            st.session_state.show_thinking = show_thinking

            use_deeper = st.checkbox(
                "使用增强版研究工具",
                value=st.session_state.get("use_deeper_tool", True),
                key="sidebar_use_deeper",
                help="启用子问题生成和多轮搜索",
            )
            st.session_state.use_deeper_tool = use_deeper
        else:
            st.session_state.show_thinking = False

        st.markdown("---")

        # === 系统设置 ===
        st.header("系统设置")

        debug_mode = st.checkbox(
            "启用调试模式",
            value=st.session_state.debug_mode,
            key="sidebar_debug_mode",
            help="显示执行轨迹、源内容和性能监控",
        )
        if debug_mode != st.session_state.debug_mode:
            st.session_state.debug_mode = debug_mode
            if debug_mode:
                st.session_state.use_stream = False

        if not debug_mode:
            use_stream = st.checkbox(
                "使用流式响应",
                value=st.session_state.get("use_stream", True),
                key="sidebar_use_stream",
                help="实时显示生成结果",
            )
            st.session_state.use_stream = use_stream
        else:
            st.session_state.use_stream = False
            st.info("调试模式下已禁用流式响应")

        st.markdown("---")

        # === 示例问题 ===
        st.header("示例问题")
        for q in EXAMPLE_QUESTIONS:
            st.markdown(f'<div class="example-question">{q}</div>', unsafe_allow_html=True)

        st.markdown("---")

        # === 项目信息 ===
        st.markdown("""
        ### 关于
        企业设备故障智能问答系统

        **调试模式**可查看:
        - 执行轨迹
        - 源内容
        - 性能监控
        """)

        if st.button("🗑️ 清除对话历史"):
            clear_chat()
            st.rerun()
