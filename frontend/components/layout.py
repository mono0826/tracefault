"""页面布局组件 — 统一各页标题、指标卡、分区样式"""

import html

import streamlit as st


def subpage_header(icon: str, title: str, caption: str = "", badge: str = ""):
    """子页面紧凑顶栏 — 标题 + 系统状态合并为一行"""
    from frontend.components.status_bar import render_status_pills

    badge_html = f'<span class="page-badge">{badge}</span>' if badge else ""
    caption_html = f'<p class="page-toolbar-caption">{caption}</p>' if caption else ""
    pills_html = render_status_pills()
    html = (
        f'<div class="page-toolbar">'
        f'<div class="page-toolbar-left">'
        f'<div class="page-toolbar-icon">{icon}</div>'
        f'<div class="page-toolbar-text">'
        f'<div class="page-toolbar-title-row">'
        f'<h1 class="page-toolbar-title">{title}</h1>{badge_html}'
        f'</div>{caption_html}'
        f'</div></div>{pills_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def page_header(icon: str, title: str, caption: str, badge: str = ""):
    """页面顶部 Hero 区（兼容旧调用，转发到紧凑顶栏）"""
    subpage_header(icon, title, caption, badge)


def metrics_row(items: list[tuple[str, str, str]], columns: int = None):
    """指标卡行 — items: [(icon, label, value), ...]"""
    n = columns or len(items)
    cols = st.columns(n)
    for col, (icon, label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-top">
                        <span class="metric-icon">{icon}</span>
                        <span class="metric-value">{value}</span>
                    </div>
                    <div class="metric-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def section_header(title: str, subtitle: str = ""):
    """分区标题"""
    sub = f'<p class="section-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="section-header"><h3 class="section-title">{title}</h3>{sub}</div>',
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, description: str):
    """空状态占位"""
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-state-icon">{icon}</div>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-desc">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_banner(text: str, variant: str = "info"):
    """提示条 — variant: info | success | warning"""
    st.markdown(f'<div class="info-banner info-banner-{variant}">{text}</div>', unsafe_allow_html=True)


def render_doc_table(docs: list[dict], *, embedded: bool = False):
    """已处理文档表格 — 序号列固定窄宽，标题/源文件按比例分配"""
    rows = "".join(
        f"<tr><td>{i}</td><td>{html.escape(d.get('title', ''))}</td>"
        f"<td>{html.escape(d.get('source_file', ''))}</td></tr>"
        for i, d in enumerate(docs, 1)
    )
    wrap_cls = "doc-table-embedded" if embedded else "doc-table-wrap"
    st.markdown(
        f'<div class="{wrap_cls}"><table class="doc-table">'
        f"<thead><tr><th>序号</th><th>标题</th><th>源文件</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def pipeline_steps():
    """知识图谱构建流程步骤（HTML 卡片）"""
    steps = [
        ("1", "构建图结构", "创建 Document / Chunk 节点与关系"),
        ("2", "提取实体关系", "LLM 从文档中提取实体和关系"),
        ("3", "写入图数据库", "将实体关系写入 Neo4j"),
        ("4", "向量索引", "为 Chunk 和 Entity 创建向量索引"),
        ("5", "实体处理", "相似检测 → 合并 → 消歧 → 对齐"),
        ("6", "社区检测", "Leiden 算法发现社区结构"),
        ("7", "社区摘要", "LLM 生成社区摘要"),
    ]
    html = '<div class="pipeline-grid">'
    for num, name, desc in steps:
        html += f"""
        <div class="pipeline-step">
            <div class="pipeline-step-num">{num}</div>
            <div class="pipeline-step-body">
                <div class="pipeline-step-name">{name}</div>
                <div class="pipeline-step-desc">{desc}</div>
            </div>
        </div>
        """
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
