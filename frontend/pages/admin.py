"""管理后台页面"""

import streamlit as st
import pandas as pd

from frontend.components.doc_management import render_document_management
from frontend.components.layout import subpage_header, metrics_row, section_header, empty_state, info_banner


subpage_header("🔐", "管理后台", "文档管理、设备台账与数据统计", badge="预览版")

tab_docs, tab1, tab2, tab3 = st.tabs(["📄 文档管理", "🏭 设备管理", "📋 故障案例", "📊 数据看板"])

# ---------- 文档管理 ----------
with tab_docs:
    render_document_management()

# ---------- 设备管理 ----------
with tab1:
    section_header("设备列表", "管理企业设备台账，支持与故障诊断联动")
    st.markdown(
        '<div class="placeholder-hint">💡 设备台账功能将在后续版本接入数据库，'
        '届时可与故障诊断页的设备编号联动。</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="filter-bar-wrap">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        st.text_input("设备名称", placeholder="🔍 搜索设备...", label_visibility="collapsed")
    with col2:
        st.selectbox("分类", ["全部", "数控机床", "机器人", "PLC"], label_visibility="collapsed")
    with col3:
        st.selectbox("状态", ["全部", "正常", "维修中", "已停机"], label_visibility="collapsed")
    with col4:
        st.button("➕ 新增", type="primary", width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    df_equip = pd.DataFrame(columns=["ID", "设备名称", "型号", "分类", "位置", "状态"])
    if df_equip.empty:
        empty_state("🏭", "暂无设备数据", "点击「新增」添加第一台设备，或等待数据库接入")
    else:
        st.dataframe(df_equip, width="stretch", hide_index=True)

# ---------- 故障案例 ----------
with tab2:
    section_header("故障案例管理", "记录与追踪设备故障诊断历史")
    st.markdown(
        '<div class="placeholder-hint">💡 故障案例库将在后续版本实现，'
        '支持从诊断页保存案例并在此统一管理。</div>',
        unsafe_allow_html=True,
    )

    df_faults = pd.DataFrame(columns=["ID", "设备", "故障标题", "严重级别", "状态", "发生时间"])
    if df_faults.empty:
        empty_state("📋", "暂无故障案例", "完成故障诊断后可保存为案例，便于后续查阅")
    else:
        st.dataframe(df_faults, width="stretch", hide_index=True)

# ---------- 数据看板 ----------
with tab3:
    section_header("故障统计分析", "全局故障趋势与处理效率概览")

    metrics_row([
        ("📊", "总故障数", "--"),
        ("📈", "本月新增", "--"),
        ("✅", "解决率", "--%"),
    ])

    with st.container(border=True):
        info_banner("详细统计图表（趋势、分布、TOP 故障类型）将在后续版本实现", "info")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 故障趋势")
            empty_state("📈", "暂无趋势数据", "接入数据库后将展示月度故障趋势图")
        with col2:
            st.markdown("##### 设备分布")
            empty_state("🏭", "暂无分布数据", "接入数据库后将展示各类型设备故障占比")
