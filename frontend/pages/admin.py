"""管理后台页面"""

import streamlit as st
import pandas as pd

st.title("🔐 管理后台")

tab1, tab2, tab3 = st.tabs(["🏭 设备管理", "📋 故障案例", "📊 数据看板"])

# ---------- 设备管理 ----------
with tab1:
    st.subheader("设备列表")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        st.text_input("设备名称", placeholder="搜索...", label_visibility="collapsed")
    with col2:
        st.selectbox("分类", ["全部", "数控机床", "机器人", "PLC"], label_visibility="collapsed")
    with col3:
        st.selectbox("状态", ["全部", "正常", "维修中", "已停机"], label_visibility="collapsed")
    with col4:
        st.button("➕ 新增设备")

    # TODO: 从数据库加载
    df_equip = pd.DataFrame(columns=["ID", "设备名称", "型号", "分类", "位置", "状态"])
    st.dataframe(df_equip, width="stretch")

# ---------- 故障案例 ----------
with tab2:
    st.subheader("故障案例管理")
    # TODO: 故障案例 CRUD
    df_faults = pd.DataFrame(columns=["ID", "设备", "故障标题", "严重级别", "状态", "发生时间"])
    st.dataframe(df_faults, width="stretch")

# ---------- 数据看板 ----------
with tab3:
    st.subheader("故障统计分析")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总故障数", "--")
    with col2:
        st.metric("本月新增", "--")
    with col3:
        st.metric("解决率", "--%")

    st.caption("详细统计功能将在后续版本实现")
