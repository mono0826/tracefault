"""知识图谱可视化组件 — 使用 pyvis 渲染交互式网络图"""

import os
import tempfile
import base64

import streamlit as st

from frontend.components.layout import section_header

KG_VIS_PANEL_HEIGHT = 780

KG_COLORS = [
    "#4285F4", "#EA4335", "#FBBC05", "#34A853",
    "#7B1FA2", "#0097A7", "#FF6D00", "#757575",
    "#607D8B", "#C2185B",
]


def _read_display_settings() -> dict:
    """从 session_state 读取显示参数（控件在左侧控制面板下方）"""
    return {
        "physics": st.session_state.get("kg_physics", True),
        "node_size": st.session_state.get("kg_node_size", 25),
        "edge_width": st.session_state.get("kg_edge_width", 3),
        "spring": st.session_state.get("kg_spring", 200),
    }


def render_display_settings():
    """物理引擎与显示参数 — 位于控制面板下方"""
    st.session_state.setdefault("kg_physics", True)
    section_header("物理引擎")
    # 第二行：节点大小
    st.slider("节点大小", 10, 50, 25, key="kg_node_size")
    # 第三行：连线宽度 + 弹簧长度
    c1, c2 = st.columns(2)
    with c1:
        st.slider("连线宽度", 1, 10, 3, key="kg_edge_width")
    with c2:
        st.slider("弹簧长度", 50, 300, 200, key="kg_spring")


def _render_legend(group_colors: dict):
    st.markdown("**图例**")
    cols = st.columns(4)
    for i, (g, c) in enumerate(group_colors.items()):
        with cols[i % 4]:
            st.markdown(
                f'<div style="display:flex;align-items:center;margin-bottom:8px">'
                f'<div style="width:16px;height:16px;border-radius:50%;'
                f'background:{c};margin-right:8px;border:1px solid #ccc;"></div>'
                f'<span style="font-size:13px">{g}</span></div>',
                unsafe_allow_html=True,
            )


def visualize_graph(kg_data: dict):
    """使用 pyvis 渲染知识图谱"""
    from pyvis.network import Network
    if not kg_data or "nodes" not in kg_data or "links" not in kg_data:
        st.warning("无法获取图谱数据")
        return
    if not kg_data["nodes"]:
        st.info("图谱中暂无实体节点")
        return

    settings = _read_display_settings()
    physics = settings["physics"]
    node_size = settings["node_size"]
    edge_width = settings["edge_width"]
    spring = settings["spring"]

    groups = sorted({n.get("group", "Unknown") for n in kg_data["nodes"]})
    group_colors = {g: KG_COLORS[i % len(KG_COLORS)] for i, g in enumerate(groups)}

    net = Network(height="600px", width="100%", bgcolor="#FFFFFF", font_color="#333333", directed=True)
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

    added_node_ids = {n["id"] for n in kg_data["nodes"]}
    for link in kg_data["links"]:
        if link["source"] not in added_node_ids or link["target"] not in added_node_ids:
            continue
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

    _render_legend(group_colors)
