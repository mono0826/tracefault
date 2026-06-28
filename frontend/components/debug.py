"""调试面板 — 执行轨迹、源内容、性能监控

注意：本面板不包含知识图谱相关的任何标签页。
"""

import json
import streamlit as st

from frontend.utils.helpers import display_source_content
from frontend.utils.performance import display_performance_stats, clear_performance_data


# =============================================================
#  执行轨迹
# =============================================================

def _display_execution_trace():
    """显示执行轨迹标签页"""
    log = st.session_state.get("execution_log", [])

    if not log:
        st.info("发送查询后将在此显示执行轨迹。")
        return

    # 检测深度研究日志格式
    has_deep = any("[深度研究]" in line for line in log)
    has_kb = any("[KB检索]" in line for line in log)

    if has_deep or has_kb:
        _display_formatted_deep_research_logs(log)
    else:
        _display_simple_logs(log)


def _display_simple_logs(log: list):
    """简单日志列表"""
    for line in log:
        if "[检索]" in line or "[生成]" in line:
            st.markdown(f"<span style='color:#1976d2;'>{line}</span>", unsafe_allow_html=True)
        elif "[错误]" in line:
            st.markdown(f"<span style='color:#d32f2f;'>{line}</span>", unsafe_allow_html=True)
        elif "[融合]" in line:
            st.markdown(f"<span style='color:#7b1fa2;'>{line}</span>", unsafe_allow_html=True)
        else:
            st.markdown(line)


def _display_formatted_deep_research_logs(log: list):
    """格式化的深度研究日志显示"""
    # 解析迭代轮次
    iterations = []
    current_round = None
    current_content = []

    for line in log:
        if "开始第" in line and "轮迭代" in line:
            if current_content:
                iterations.append({"round": current_round, "content": current_content})
            import re
            m = re.search(r"开始第(\d+)轮迭代", line)
            current_round = int(m.group(1)) if m else None
            current_content = [line]
        elif "结束迭代" in line:
            current_content.append(line)
        else:
            current_content.append(line)

    if current_content:
        iterations.append({"round": current_round, "content": current_content})

    if not iterations:
        _display_simple_logs(log)
        return

    # 轮次选择器
    st.markdown("#### 选择迭代轮次")
    valid = [it for it in iterations if it["round"] is not None]
    if not valid:
        _display_simple_logs(log)
        return

    opts = {f"第 {it['round']} 轮迭代": it for it in valid}
    default_key = next((k for k in opts if "1 轮" in k), list(opts.keys())[0])
    selected = st.selectbox("选迭代轮次", list(opts.keys()), index=list(opts.keys()).index(default_key))

    iteration = opts[selected]
    lines = iteration.get("content", [])

    # 分类展示
    queries = []
    kb_searches = []
    kb_results = []
    useful_info = None
    other = []

    for line in lines:
        if "执行查询:" in line:
            queries.append(line.split("执行查询:")[-1].strip())
        elif "[KB检索] 开始搜索:" in line:
            kb_searches.append(line.split("开始搜索:")[-1].strip())
        elif "[KB检索] 结果:" in line:
            kb_results.append(line)
        elif "发现有用信息:" in line:
            useful_info = line.split("发现有用信息:")[-1].strip()
        else:
            other.append(line)

    # 查询
    if queries:
        st.markdown("##### 执行的查询")
        for q in queries:
            st.markdown(
                f'<div style="background:#f5f5f5; padding:8px; border-left:4px solid #4CAF50; '
                f'margin:8px 0; border-radius:3px;">{q}</div>',
                unsafe_allow_html=True,
            )

    # 有用信息
    if useful_info:
        st.markdown("##### 发现的有用信息")
        st.markdown(
            f'<div style="background:#E8F5E9; padding:10px; border-left:4px solid #4CAF50; '
            f'margin:10px 0; border-radius:4px;">{useful_info}</div>',
            unsafe_allow_html=True,
        )

    # KB 检索
    if kb_searches or kb_results:
        st.markdown("##### 知识库检索")
        c1, c2 = st.columns(2)
        with c1:
            for s in kb_searches:
                st.markdown(
                    f'<div style="background:#FFF8E1; padding:8px; border-left:4px solid #FFA000; '
                    f'margin:8px 0; border-radius:3px;">{s}</div>',
                    unsafe_allow_html=True,
                )
        with c2:
            for r in kb_results:
                st.markdown(f"<span style='color:#f57c00;'>{r}</span>", unsafe_allow_html=True)

    # 其他详细日志
    if other:
        with st.expander("详细日志", expanded=False):
            for line in other:
                if "[KB检索]" in line:
                    st.markdown(f'<div style="padding:2px 0; color:#f57c00;">{line}</div>',
                                unsafe_allow_html=True)
                elif "[深度研究]" in line:
                    st.markdown(f'<div style="padding:2px 0; color:#1976d2;">{line}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="padding:2px 0; color:#666;">{line}</div>',
                                unsafe_allow_html=True)


# =============================================================
#  源内容
# =============================================================

def _display_source_content():
    """显示源内容标签页"""
    content = st.session_state.get("source_content", None)
    if content:
        with st.container():
            st.markdown('<div class="source-content-container">', unsafe_allow_html=True)
            display_source_content(content)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("在调试模式下，点击 AI 回答中的「加载」按钮查看源文本内容。")


# =============================================================
#  性能监控
# =============================================================

def _display_performance():
    """显示性能监控标签页"""
    st.markdown('<div class="debug-header">性能统计</div>', unsafe_allow_html=True)
    display_performance_stats()
    if st.button("清除性能数据"):
        clear_performance_data()
        st.rerun()


# =============================================================
#  主面板
# =============================================================

def display_debug_panel():
    """显示调试面板（不含知识图谱相关标签）"""
    st.subheader("🔍 调试信息")

    # 三个标签页：执行轨迹、源内容、性能监控
    tabs = st.tabs(["执行轨迹", "源内容", "性能监控"])

    with tabs[0]:
        _display_execution_trace()

    with tabs[1]:
        _display_source_content()

    with tabs[2]:
        _display_performance()
