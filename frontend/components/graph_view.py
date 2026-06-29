"""知识图谱可视化组件 — 使用 pyvis 渲染交互式网络图"""

from pathlib import Path
import tempfile, os, hashlib, time, base64

import streamlit as st
from pyvis.network import Network

# 颜色调色板
KG_COLORS = [
    "#4285F4", "#EA4335", "#FBBC05", "#34A853",
    "#7B1FA2", "#0097A7", "#FF6D00", "#757575",
    "#607D8B", "#C2185B",
]


def visualize_graph(kg_data: dict):
    """使用 pyvis 渲染知识图谱"""
    if not kg_data or "nodes" not in kg_data or "links" not in kg_data:
        st.warning("无法获取图谱数据")
        return
    if not kg_data["nodes"]:
        st.info("图谱中暂无实体节点")
        return

    # 显示设置
    with st.expander("⚙️ 显示设置", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            physics = st.checkbox("物理引擎", value=True, key="kg_physics")
            node_size = st.slider("节点大小", 10, 50, 25, key="kg_node_size")
        with col2:
            edge_width = st.slider("连线宽度", 1, 10, 3, key="kg_edge_width")
            spring = st.slider("弹簧长度", 50, 300, 200, key="kg_spring")

    # 建立 group → color 映射
    groups = sorted({n.get("group", "Unknown") for n in kg_data["nodes"]})
    group_colors = {}
    for i, g in enumerate(groups):
        group_colors[g] = KG_COLORS[i % len(KG_COLORS)]

    # 创建网络图
    net = Network(height="600px", width="100%", bgcolor="#FFFFFF",
                  font_color="#333333", directed=True)

    # vis-network 配置
    net.set_options(f"""
    {{
      "physics": {{
        "enabled": {str(physics).lower()},
        "barnesHut": {{
          "gravitationalConstant": -3000,
          "centralGravity": 0.5,
          "springLength": {spring},
          "springConstant": 0.04,
          "damping": 0.15
        }},
        "solver": "barnesHut",
        "stabilization": {{"enabled": true, "iterations": 1000}}
      }},
      "interaction": {{
        "navigationButtons": true,
        "hover": true,
        "tooltipDelay": 200
      }}
    }}
    """)

    # 添加节点
    for n in kg_data["nodes"]:
        color = group_colors.get(n.get("group", "Unknown"), KG_COLORS[0])
        desc = n.get("description", "")
        net.add_node(
            n["id"],
            label=n.get("label", n["id"]),
            title=f"{n.get('label', n['id'])}{(': ' + desc) if desc else ''}",
            color={"background": color, "border": "#ffffff",
                   "highlight": {"background": color, "border": "#000000"}},
            size=node_size,
            font={"color": "#ffffff", "size": 14, "face": "Arial"},
            borderWidth=2,
        )

    # 添加边
    for link in kg_data["links"]:
        w = float(link.get("weight", 1))
        width = edge_width * min(1 + w * 0.2, 3)
        net.add_edge(
            link["source"], link["target"],
            title=link.get("description", link.get("label", "")),
            label=link.get("label", ""),
            width=width,
            color={"color": "#999999", "highlight": "#666666"},
            arrowStrikethrough=False,
        )

    # 渲染
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html = f.read()
        b64 = base64.b64encode(html.encode("utf-8")).decode()
        st.iframe(f"data:text/html;base64,{b64}", height=600)
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    # 图例
    st.write("### 图例")
    cols = st.columns(4)
    for i, (g, c) in enumerate(group_colors.items()):
        with cols[i % 4]:
            st.markdown(
                f'<div style="display:flex;align-items:center;margin-bottom:8px">'
                f'<div style="width:16px;height:16px;border-radius:50%;'
                f'background:{c};margin-right:8px;border:1px solid #ccc;"></div>'
                f'<span>{g}</span></div>',
                unsafe_allow_html=True,
            )
