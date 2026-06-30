"""知识图谱构建 — 步骤进度 + 终端输出可视化"""

import html
import streamlit as st

PIPELINE_STEPS = [
    {"id": "clear", "name": "清除旧索引", "desc": "清理 Neo4j 中过期的向量索引"},
    {"id": "graph", "name": "构建图结构", "desc": "Document / Chunk 节点，LLM 提取实体关系"},
    {"id": "index", "name": "实体索引与社区", "desc": "向量索引 + Leiden 社区检测与摘要"},
    {"id": "chunk", "name": "Chunk 索引", "desc": "为文本块创建向量索引"},
]

_STATUS_LABEL = {
    "pending": ("○", "等待"),
    "running": ("▶", "进行中"),
    "done": ("✓", "完成"),
    "error": ("✗", "失败"),
    "skipped": ("—", "跳过"),
}


def init_pipeline_state():
    defaults = {s["id"]: "pending" for s in PIPELINE_STEPS}
    st.session_state.setdefault("kg_pipeline_logs", [])
    st.session_state.setdefault("kg_pipeline_status", "就绪 — 选择输入源后点击「开始构建」")
    st.session_state.setdefault("kg_pipeline_step_states", defaults)
    st.session_state.setdefault("kg_pipeline_current", None)


def reset_pipeline_state():
    st.session_state.kg_pipeline_logs = []
    st.session_state.kg_pipeline_status = "正在启动..."
    st.session_state.kg_pipeline_step_states = {s["id"]: "pending" for s in PIPELINE_STEPS}
    st.session_state.kg_pipeline_current = None


def set_step_state(step_id: str, state: str):
    st.session_state.kg_pipeline_step_states[step_id] = state
    if state == "running":
        st.session_state.kg_pipeline_current = step_id


def render_pipeline_progress():
    """左侧：步骤列表，高亮当前步骤"""
    states = st.session_state.get("kg_pipeline_step_states", {})
    current = st.session_state.get("kg_pipeline_current")

    for i, step in enumerate(PIPELINE_STEPS, 1):
        sid = step["id"]
        state = states.get(sid, "pending")
        if sid == current and state == "running":
            css = "running"
        else:
            css = state
        icon, _ = _STATUS_LABEL.get(state, ("○", ""))

        st.markdown(
            f"""
            <div class="pipeline-step-card {css}">
                <div class="pipeline-step-row">
                    <span class="pipeline-step-badge">{icon} {i}</span>
                    <div>
                        <div class="pipeline-step-name">{step["name"]}</div>
                        <div class="pipeline-step-desc">{step["desc"]}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _format_terminal_html(logs: list[str], status: str) -> str:
    body = "\n".join(logs) if logs else "$ waiting for pipeline start..."
    return (
        f'<div class="terminal-panel" style="width:100%;min-height:560px;display:flex;flex-direction:column;">'
        f'<div class="terminal-header">'
        f'<span class="terminal-dot red"></span>'
        f'<span class="terminal-dot yellow"></span>'
        f'<span class="terminal-dot green"></span>'
        f'<span class="terminal-title">build.log</span>'
        f'</div>'
        f'<div class="terminal-body" style="flex:1;min-height:480px;max-height:72vh;overflow-y:auto;">'
        f'{html.escape(body)}'
        f'</div>'
        f'<div class="terminal-status">&gt;&gt;&gt; {html.escape(status)}</div>'
        f'</div>'
    )


def render_terminal_panel():
    """右侧：终端风格日志（静态，读取 session_state）"""
    logs = st.session_state.get("kg_pipeline_logs", [])
    status = st.session_state.get("kg_pipeline_status", "就绪")
    st.markdown(_format_terminal_html(logs, status), unsafe_allow_html=True)


def make_pipeline_callbacks(progress_bar, terminal_placeholder, logs: list, steps_placeholder=None):
    """创建 run_pipeline 回调，实时刷新终端（可选步骤面板）"""

    def _refresh_ui():
        if steps_placeholder is not None:
            with steps_placeholder.container():
                render_pipeline_progress()
        terminal_placeholder.markdown(
            _format_terminal_html(logs, st.session_state.get("kg_pipeline_status", "")),
            unsafe_allow_html=True,
        )

    def on_status(msg: str, pct: float):
        st.session_state.kg_pipeline_status = msg
        progress_bar.progress(min(max(pct, 0.0), 1.0), text=msg)
        _refresh_ui()

    def on_log(msg: str):
        logs.append(msg)
        st.session_state.kg_pipeline_logs = list(logs)
        _refresh_ui()

    def on_step_start(step_id: str, msg: str, pct: float):
        set_step_state(step_id, "running")
        on_status(msg, pct)

    def on_step_end(step_id: str, ok: bool = True, skipped: bool = False):
        if skipped:
            set_step_state(step_id, "skipped")
        else:
            set_step_state(step_id, "done" if ok else "error")
        _refresh_ui()

    return on_status, on_log, on_step_start, on_step_end
