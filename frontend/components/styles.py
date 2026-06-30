"""自定义 CSS — 工业风 × 豆包布局"""

import streamlit as st


def custom_css():
    """注入全局样式。Streamlit 1.57+ 须覆盖 stMainBlockContainer 的 6rem 顶栏留白。"""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --ind-bg: #e8ecf1;
        --ind-surface: #ffffff;
        --ind-sidebar: #141c28;
        --ind-sidebar-hover: #1e2a3a;
        --ind-border: #d4dbe5;
        --ind-text: #1a2332;
        --ind-text-muted: #64748b;
        --ind-accent: #2563eb;
        --ind-accent-hover: #1d4ed8;
        --ind-warn: #ea580c;
        --ind-success: #059669;
        --ind-radius: 10px;
        --ind-radius-lg: 14px;
        --chat-max: 780px;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .stApp { background: var(--ind-bg); }
    footer, #MainMenu { visibility: hidden; }
    /* 保留顶栏以显示侧栏折叠/展开按钮，仅隐藏装饰与 Deploy */
    header[data-testid="stHeader"] {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
        padding: 0 !important;
        margin: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }
    header[data-testid="stHeader"] [data-testid="stToolbar"],
    header[data-testid="stHeader"] [data-testid="stDecoration"],
    header[data-testid="stHeader"] [data-testid="stStatusWidget"],
    header[data-testid="stHeader"] .stAppDeployButton {
        display: none !important;
    }
    /* 侧栏始终展开，禁用折叠（避免收起后无法打开） */
    section[data-testid="stSidebar"] {
        transform: none !important;
        min-width: 18rem !important;
        max-width: 21rem !important;
        visibility: visible !important;
    }
    section[data-testid="stSidebar"][aria-expanded="false"] {
        transform: none !important;
        min-width: 18rem !important;
        margin-left: 0 !important;
    }
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stExpandSidebarButton"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    [data-testid="stSidebarHeader"] {
        display: none !important;
    }

    /* Streamlit 1.57+ 主内容区 — 默认 padding-top 6rem 为顶栏预留，需强制覆盖 */
    [data-testid="stMainBlockContainer"],
    .stMainBlockContainer.block-container {
        padding-top: 0.35rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) {
        max-width: min(96vw, 1600px) !important;
        padding-top: 0.2rem !important;
    }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) div[data-testid="stMarkdown"] { width: 100%; }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) div[data-testid="stMarkdown"] > div { width: 100%; max-width: 100%; }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) [data-testid="stTabs"] { margin-top: -6px; }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) .section-header { margin: 0 0 10px 0; }
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) div[data-testid="stVerticalBlockBorderWrapper"] { margin-bottom: 10px; }
    /* 主内容顶层紧凑 */
    [data-testid="stMainBlockContainer"]:has(.page-toolbar) > div[data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }

    /* 兼容旧版选择器 */
    [data-testid="stAppViewBlockContainer"],
    .main .block-container {
        padding-top: 0.35rem !important;
    }

    /* ===== 侧边栏：工业深色 ===== */
    section[data-testid="stSidebar"] {
        background: var(--ind-sidebar) !important;
        border-right: 1px solid #0f1419 !important;
    }
    section[data-testid="stSidebar"] .block-container { padding: 0.75rem 0.85rem 1.5rem; }
    section[data-testid="stSidebar"] * { color: #cbd5e1; }
    section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] small {
        color: #94a3b8 !important;
    }

    div[data-testid="stSidebarNav"] {
        background: rgba(255,255,255,0.03);
        border-radius: var(--ind-radius);
        padding: 6px;
        margin-bottom: 12px;
    }
    div[data-testid="stSidebarNav"] a {
        color: #94a3b8 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        padding: 8px 10px !important;
    }
    div[data-testid="stSidebarNav"] a:hover {
        background: var(--ind-sidebar-hover) !important;
        color: #f1f5f9 !important;
    }
    div[data-testid="stSidebarNav"] a[aria-current="page"] {
        background: var(--ind-accent) !important;
        color: #fff !important;
        font-weight: 600 !important;
    }

    .ind-brand {
        display: flex; align-items: center; gap: 10px;
        padding: 8px 4px 14px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 12px;
    }
    .ind-brand-icon {
        width: 38px; height: 38px;
        background: linear-gradient(145deg, #2563eb, #1e40af);
        border-radius: 9px;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px;
        box-shadow: 0 2px 8px rgba(37,99,235,0.35);
    }
    .ind-brand-text { flex: 1; }
    .ind-brand-name { font-size: 15px; font-weight: 700; color: #f1f5f9 !important; }
    .ind-brand-tag {
        font-size: 10px; color: #64748b !important;
        letter-spacing: 0.5px; text-transform: uppercase; margin-top: 2px;
    }

    .ind-section-label {
        font-size: 11px; font-weight: 600; color: #64748b !important;
        text-transform: uppercase; letter-spacing: 0.8px;
        margin: 16px 0 8px; padding: 0 4px;
    }

    .ind-new-chat button {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #e2e8f0 !important;
        border-radius: 9px !important;
        font-size: 13px !important;
        padding: 9px 12px !important;
        text-align: left !important;
    }
    .ind-new-chat button:hover {
        background: rgba(37,99,235,0.2) !important;
        border-color: rgba(37,99,235,0.5) !important;
    }

    .ind-history-active button {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #f8fafc !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
        text-align: left !important;
    }

    section[data-testid="stSidebar"] .ind-example-btn button {
        background: transparent !important;
        border: none !important;
        color: #94a3b8 !important;
        font-size: 12px !important;
        padding: 6px 8px !important;
        border-radius: 6px !important;
        text-align: left !important;
        white-space: normal !important;
        height: auto !important;
        line-height: 1.4 !important;
    }
    section[data-testid="stSidebar"] .ind-example-btn button:hover {
        background: rgba(255,255,255,0.06) !important;
        color: #e2e8f0 !important;
    }

    section[data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: rgba(255,255,255,0.06) !important;
        border-color: rgba(255,255,255,0.12) !important;
        color: #e2e8f0 !important;
    }

    .ind-sidebar-meta {
        margin-top: 16px; padding-top: 12px;
        border-top: 1px solid rgba(255,255,255,0.08);
        font-size: 11px; line-height: 1.6; color: #64748b !important;
    }

    /* ===== 对话主区 ===== */
    .chat-shell-marker { display: none; }

    .chat-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 4px 10px;
        border-bottom: 1px solid var(--ind-border);
        margin-bottom: 8px;
        background: var(--ind-bg);
    }
    .chat-header-center { flex: 1; text-align: center; }
    .chat-header-title {
        font-size: 15px; font-weight: 600; color: var(--ind-text);
    }
    .chat-header-badge {
        display: inline-block; margin-top: 4px;
        font-size: 11px; color: var(--ind-text-muted);
        background: var(--ind-surface);
        border: 1px solid var(--ind-border);
        padding: 2px 10px; border-radius: 12px;
    }

    .chat-thread-marker { display: none; }

    .welcome-industrial {
        text-align: center;
        padding: 16px 20px 8px;
        max-width: var(--chat-max);
        margin: 0 auto 8px;
    }
    .welcome-industrial .wi-icon {
        width: 64px; height: 64px; margin: 0 auto 20px;
        background: linear-gradient(145deg, #1e293b, #334155);
        border-radius: 16px;
        display: flex; align-items: center; justify-content: center;
        font-size: 28px;
        box-shadow: 0 8px 24px rgba(26,35,50,0.15);
    }
    .welcome-industrial .wi-title {
        font-size: 22px; font-weight: 700; color: var(--ind-text);
        margin-bottom: 10px;
    }
    .welcome-industrial .wi-desc {
        font-size: 14px; color: var(--ind-text-muted); line-height: 1.7;
    }
    .welcome-industrial .wi-tags {
        display: flex; flex-wrap: wrap; gap: 8px;
        justify-content: center; margin-top: 28px;
    }
    .welcome-industrial .wi-tag {
        background: var(--ind-surface);
        border: 1px solid var(--ind-border);
        padding: 6px 14px; border-radius: 20px;
        font-size: 12px; color: var(--ind-text-muted);
    }

    /* 聊天气泡 */
    div[data-testid="stChatMessage"] {
        background: transparent !important;
        padding: 6px 0 !important;
        gap: 12px !important;
    }
    div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] {
        background: var(--ind-accent);
        color: #fff !important;
        padding: 10px 16px;
        border-radius: 16px 16px 4px 16px;
        max-width: 85%;
        margin-left: auto;
        box-shadow: 0 2px 8px rgba(37,99,235,0.2);
    }
    div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] p {
        color: #fff !important;
    }
    div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] {
        background: var(--ind-surface);
        border: 1px solid var(--ind-border);
        padding: 14px 18px;
        border-radius: 4px 16px 16px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        font-size: 14px; line-height: 1.75; color: var(--ind-text);
    }
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h1,
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h2,
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h3 {
        color: var(--ind-text) !important;
        font-size: 1em !important;
        font-weight: 600 !important;
        margin-top: 0.8em !important;
    }
    div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] code {
        background: #f1f5f9; color: #c2410c;
        padding: 2px 6px; border-radius: 4px;
        font-family: 'Consolas', 'Monaco', monospace; font-size: 13px;
    }

    /* 输入 dock — 勿用 min-height / flex:auto，Streamlit 组件不在 HTML div 内 */
    .input-dock-marker { display: none; }

    .input-dock-panel {
        background: var(--ind-surface);
        border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius-lg);
        padding: 12px 14px 4px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        max-width: var(--chat-max);
        margin: 16px auto 0;
    }
    .input-dock-label {
        font-size: 11px; font-weight: 600; color: var(--ind-text-muted);
        text-transform: uppercase; letter-spacing: 0.5px;
        margin-bottom: 8px;
    }

    div[data-testid="column"] .dock-pill button {
        background: #f8fafc !important;
        border: 1px solid var(--ind-border) !important;
        color: var(--ind-text) !important;
        border-radius: 16px !important;
        font-size: 12px !important;
        padding: 4px 10px !important;
        min-height: 28px !important;
    }
    div[data-testid="column"] .dock-pill button:hover {
        border-color: var(--ind-accent) !important;
        color: var(--ind-accent) !important;
        background: #eff6ff !important;
    }

    div[data-testid="stChatInput"] {
        border: none !important; padding: 4px 0 0 !important; background: transparent !important;
    }
    div[data-testid="stChatInput"] > div {
        border: 1px solid var(--ind-border) !important;
        border-radius: 12px !important;
        background: #fafbfc !important;
    }
    div[data-testid="stChatInput"] textarea {
        font-size: 14px !important; color: var(--ind-text) !important;
    }
    div[data-testid="stChatInput"] button {
        background: var(--ind-accent) !important;
        color: white !important;
        border-radius: 10px !important;
    }
    div[data-testid="stChatInput"] button:hover {
        background: var(--ind-accent-hover) !important;
    }

    /* 折叠面板 */
    div[data-testid="stExpander"] {
        background: var(--ind-surface);
        border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius);
        margin-bottom: 8px;
    }
    div[data-testid="stExpander"] summary {
        font-size: 12px; color: var(--ind-text-muted);
    }

    .source-ref-box {
        background: #f8fafc; border-left: 3px solid var(--ind-warn);
        padding: 6px 10px; border-radius: 4px;
        font-size: 11px; font-family: monospace; color: var(--ind-text-muted);
        margin: 4px 0;
    }

    /* 子页面顶栏 */
    .page-toolbar {
        display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px 16px;
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid var(--ind-border); border-radius: var(--ind-radius-lg);
        padding: 10px 16px; margin: 0 0 10px 0;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .page-toolbar-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
    .page-toolbar-icon {
        width: 38px; height: 38px; background: linear-gradient(145deg, #1e293b, #334155);
        border-radius: 10px; display: flex; align-items: center; justify-content: center;
        font-size: 1.15rem; flex-shrink: 0;
    }
    .page-toolbar-text { min-width: 0; }
    .page-toolbar-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .page-toolbar-title {
        color: var(--ind-text) !important; font-size: 1.1rem !important;
        font-weight: 700 !important; margin: 0 !important; line-height: 1.3 !important;
    }
    .page-toolbar-caption {
        color: var(--ind-text-muted); font-size: 12px; margin: 2px 0 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .toolbar-pills { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: flex-end; }
    .toolbar-pill {
        display: inline-flex; align-items: center; gap: 6px;
        background: #fff; border: 1px solid var(--ind-border); border-radius: 20px;
        padding: 4px 12px; font-size: 11px; color: var(--ind-text-muted); white-space: nowrap;
    }
    .toolbar-pill .status-dot { margin-right: 2px; }

    .status-bar {
        display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
        background: var(--ind-surface); border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius); padding: 10px 16px; margin-bottom: 18px;
        font-size: 12px; color: var(--ind-text-muted);
    }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
    .status-dot-ok { background: var(--ind-success); }
    .status-dot-error { background: #ef4444; }

    .page-hero {
        display: flex; justify-content: space-between; align-items: center;
        background: var(--ind-surface); border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius-lg); padding: 18px 22px; margin-bottom: 20px;
    }
    .page-hero-left { display: flex; align-items: center; gap: 14px; }
    .page-hero-icon {
        width: 46px; height: 46px; background: #1e293b; border-radius: 10px;
        display: flex; align-items: center; justify-content: center; font-size: 1.4rem;
    }
    .page-hero-title { color: var(--ind-text) !important; font-size: 1.35rem !important; font-weight: 700 !important; margin: 0 !important; }
    .page-hero-caption { color: var(--ind-text-muted); font-size: 13px; margin: 4px 0 0; }
    .page-badge { background: #eff6ff; color: var(--ind-accent); padding: 3px 10px; border-radius: 12px; font-size: 10px; font-weight: 600; }

    .metric-card {
        background: var(--ind-surface); border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius); padding: 10px 14px; margin-bottom: 6px;
        transition: box-shadow 0.15s;
    }
    .metric-card:hover { box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06); }
    .metric-top { display: flex; align-items: center; gap: 8px; }
    .metric-icon { font-size: 1rem; opacity: 0.85; }
    .metric-value { font-size: 1.35rem; font-weight: 700; color: var(--ind-text); line-height: 1.2; }
    .metric-label { font-size: 11px; color: var(--ind-text-muted); margin-top: 2px; }

    .section-title { color: var(--ind-text) !important; font-size: 0.95rem !important; font-weight: 600 !important; margin: 0 !important; }
    .section-subtitle { color: var(--ind-text-muted); font-size: 11px; margin: 2px 0 0; }

    .empty-state {
        text-align: center; padding: 40px 20px;
        background: var(--ind-surface); border: 1px dashed var(--ind-border);
        border-radius: var(--ind-radius-lg); margin: 12px 0;
    }
    .empty-state-title { font-size: 14px; font-weight: 600; color: var(--ind-text); }
    .empty-state-desc { font-size: 12px; color: var(--ind-text-muted); margin-top: 4px; }

    .info-banner { padding: 10px 14px; border-radius: 8px; font-size: 13px; margin: 8px 0; }
    .info-banner-info { background: #eff6ff; color: #1d4ed8; }
    .info-banner-success { background: #ecfdf5; color: #047857; }
    .info-banner-warning { background: #fff7ed; color: #c2410c; }

    .pipeline-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
    .pipeline-step {
        display: flex; gap: 10px; background: var(--ind-surface);
        border: 1px solid var(--ind-border); border-radius: var(--ind-radius); padding: 12px;
    }
    .pipeline-step-num {
        width: 24px; height: 24px; background: #1e293b; color: #fff;
        border-radius: 6px; display: flex; align-items: center; justify-content: center;
        font-size: 11px; font-weight: 700; flex-shrink: 0;
    }
    .pipeline-step-name { font-size: 13px; font-weight: 600; color: var(--ind-text); }
    .pipeline-step-desc { font-size: 11px; color: var(--ind-text-muted); }

    .pipeline-step-card {
        background: var(--ind-surface); border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius); padding: 12px 14px; margin-bottom: 8px;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .pipeline-step-card.pending { opacity: 0.55; }
    .pipeline-step-card.running {
        border-color: var(--ind-accent); box-shadow: 0 0 0 1px rgba(37,99,235,0.15);
        background: #eff6ff;
    }
    .pipeline-step-card.done { border-color: #86efac; background: #f0fdf4; }
    .pipeline-step-card.error { border-color: #fca5a5; background: #fef2f2; }
    .pipeline-step-card.skipped { opacity: 0.45; border-style: dashed; }
    .pipeline-step-row { display: flex; gap: 12px; align-items: flex-start; }
    .pipeline-step-badge {
        min-width: 36px; height: 36px; border-radius: 8px; background: #1e293b; color: #fff;
        display: flex; align-items: center; justify-content: center;
        font-size: 12px; font-weight: 700; flex-shrink: 0;
    }
    .pipeline-step-card.running .pipeline-step-badge { background: var(--ind-accent); }
    .pipeline-step-card.done .pipeline-step-badge { background: #16a34a; }
    .pipeline-step-card.error .pipeline-step-badge { background: #dc2626; }

    .terminal-panel {
        width: 100% !important;
        max-width: 100% !important;
        min-height: 560px !important;
        box-sizing: border-box;
        display: flex !important;
        flex-direction: column !important;
        background: #0f172a; border-radius: 10px; overflow: hidden;
        border: 1px solid #334155; font-family: "Cascadia Code", "Consolas", monospace;
        margin: 8px 0 12px;
    }
    .terminal-header {
        display: flex; align-items: center; gap: 6px;
        padding: 8px 12px; background: #1e293b; border-bottom: 1px solid #334155;
    }
    .terminal-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .terminal-dot.red { background: #ef4444; }
    .terminal-dot.yellow { background: #eab308; }
    .terminal-dot.green { background: #22c55e; }
    .terminal-title { margin-left: 8px; font-size: 11px; color: #94a3b8; }
    .terminal-body {
        flex: 1 1 auto !important;
        margin: 0; padding: 14px 16px; min-height: 480px !important; max-height: 72vh !important;
        overflow-y: auto; color: #e2e8f0; font-size: 12px; line-height: 1.55;
        white-space: pre-wrap; word-break: break-word;
    }
    div[data-testid="stMarkdownContainer"] .terminal-panel,
    div[data-testid="stMarkdown"] .terminal-panel {
        width: 100% !important;
        min-height: 560px !important;
    }
    .terminal-status {
        padding: 8px 16px; background: #1e293b; border-top: 1px solid #334155;
        color: #38bdf8; font-size: 12px;
    }

    .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--ind-border); }
    .stTabs [data-baseweb="tab"] { color: var(--ind-text-muted); font-weight: 500; }
    .stTabs [aria-selected="true"] { color: var(--ind-accent) !important; border-bottom: 2px solid var(--ind-accent) !important; }

    .debug-panel-wrap {
        background: var(--ind-surface); border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius-lg); padding: 14px;
    }

    button[kind="primary"] {
        background: var(--ind-accent) !important; border-color: var(--ind-accent) !important;
        border-radius: 8px !important;
    }

    .upload-success { background: #ecfdf5; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #047857; }
    .placeholder-hint { background: #fff7ed; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #c2410c; margin-bottom: 12px; }

    .build-panel-label {
        font-size: 12px; font-weight: 700; color: var(--ind-text-muted);
        text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 8px 0;
    }
    .build-panel-hint {
        font-size: 12px; color: var(--ind-accent); margin: 6px 0 0 0;
        padding: 6px 10px; background: #eff6ff; border-radius: 6px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    /* 构建控制台：Material 图标尺寸统一 */
    div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"] svg,
    div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"] svg {
        width: 16px !important; height: 16px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--ind-border) !important; border-radius: var(--ind-radius) !important;
    }
    div[data-testid="stDataFrame"] { border: 1px solid var(--ind-border); border-radius: var(--ind-radius); }

    /* 已处理文档表格 */
    .doc-table-block { margin-bottom: 4px; }
    .doc-table-wrap {
        border: 1px solid var(--ind-border);
        border-radius: var(--ind-radius);
        background: var(--ind-surface);
    }
    .doc-table-scroll {
        --doc-table-row-h: 41px;
        --doc-table-head-h: 41px;
        max-height: calc(var(--doc-table-head-h) + var(--doc-table-row-h) * 14);
        overflow-x: auto;
        overflow-y: auto;
    }
    .doc-table-scroll .doc-table thead th {
        position: sticky;
        top: 0;
        z-index: 2;
        background: #f8fafc;
        box-shadow: 0 1px 0 var(--ind-border);
    }
    .doc-table-embedded {
        overflow-x: auto;
        background: var(--ind-surface);
    }
    .doc-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 13px;
        color: var(--ind-text);
    }
    .doc-table th,
    .doc-table td {
        padding: 10px 12px;
        border-bottom: 1px solid var(--ind-border);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .doc-table th {
        background: #f8fafc;
        font-weight: 600;
        color: var(--ind-text-muted);
        font-size: 12px;
        text-align: center;
    }
    .doc-table td { text-align: left; }
    .doc-table tbody tr:last-child td { border-bottom: 1px solid var(--ind-border); }
    .doc-table th:first-child,
    .doc-table td:first-child {
        width: 56px;
        max-width: 56px;
        text-align: center;
        padding-left: 6px;
        padding-right: 6px;
    }
    .doc-table th:nth-child(2),
    .doc-table td:nth-child(2) { width: 36%; }
    .doc-table th:nth-child(3),
    .doc-table td:nth-child(3) { width: auto; }
    .doc-table-foot {
        margin: 8px 2px 0;
        font-size: 12px;
        color: var(--ind-text-muted);
        text-align: right;
    }
    </style>
    """, unsafe_allow_html=True)
