"""主聊天界面 — 工业风 × 豆包居中对话布局"""

import uuid
import re
import html
import traceback
import streamlit as st

from frontend.common.constants import QUICK_QUESTION
from frontend.common.session import reconcile_processing_lock
from frontend.utils.helpers import (
    build_enriched_query,
    extract_source_ids,
    format_source_display_names,
    format_stream_body,
    sanitize_answer_text,
    collect_source_paths,
    _has_incomplete_citation_tail,
)
from frontend.utils.api_client import (
    chat_qa,
    chat_qa_stream,
    send_feedback,
    search_sources,
    persist_session_agent_type,
)




def _thinking_indicator_html(text: str = "思考中…") -> str:
    return (
        f'<div class="llm-thinking">'
        f'<span class="llm-thinking-spinner"></span>'
        f'<span class="llm-thinking-text">{html.escape(text)}</span>'
        f"</div>"
    )


def _stream_assistant_response(generator, *, label: str = "思考中…") -> tuple[str, list[str]]:
    """流式输出正文；引用信息全程缓存，完成后返回供「参考来源」展示"""
    slot = st.empty()
    slot.markdown(_thinking_indicator_html(label), unsafe_allow_html=True)
    parts: list[str] = []
    saved_sources: list[str] = []
    try:
        for chunk in generator:
            text = chunk if isinstance(chunk, str) else str(chunk)
            parts.append(text)
            accumulated = "".join(parts)
            st.session_state._stream_partial = accumulated
            saved_sources = collect_source_paths(accumulated)
            st.session_state._pending_sources = saved_sources

            display = format_stream_body(accumulated)
            if display.strip():
                slot.markdown(display)
            elif accumulated.strip() and _has_incomplete_citation_tail(accumulated):
                slot.markdown(_thinking_indicator_html("整理引用来源…"), unsafe_allow_html=True)
    finally:
        full = "".join(parts)
        saved_sources = collect_source_paths(full)
        st.session_state._pending_sources = saved_sources
        if full.strip():
            slot.markdown(sanitize_answer_text(full))
        else:
            slot.empty()
    return full, saved_sources


def _render_source_expander(
    display_names: list[str],
    source_ids: list[str] | None = None,
    *,
    key_suffix: str = "",
):
    if not display_names:
        return
    source_ids = source_ids or display_names
    with st.expander(f"📎 参考来源 · {len(display_names)}", expanded=False):
        for name in display_names[:8]:
            st.markdown(f'<div class="source-ref-box">{html.escape(name)}</div>', unsafe_allow_html=True)
        if st.session_state.debug_mode:
            for s_idx, sid in enumerate(source_ids):
                label = (format_source_display_names([sid])[0] if sid else "")[:12]
                if st.button(f"查看原文 {label}…", key=f"src_{sid}_{key_suffix}_{s_idx}"):
                    results = search_sources(sid, top_k=1)
                    if results:
                        st.session_state.source_content = results[0]["content"]
                        st.rerun()


def _display_thinking_process(raw_thinking: str):
    lines = raw_thinking.split("\n")
    st.markdown("\n".join(f"> {line}" for line in lines))


def _get_enriched_query(display_prompt: str) -> str:
    return build_enriched_query(
        display_prompt,
        equipment_type=st.session_state.get("equipment_type", ""),
        equipment_id=st.session_state.get("equipment_id", ""),
        fault_severity=st.session_state.get("fault_severity", ""),
    )


def _chat_history_for_api() -> list | None:
    """当前轮之前的对话历史，供意图识别使用"""
    msgs = st.session_state.get("messages", [])
    if len(msgs) <= 1:
        return None
    prior = msgs[:-1]
    return [{"role": m["role"], "content": m["content"]} for m in prior if m["role"] in ("user", "assistant")]


def _render_welcome():
    st.markdown(
        """
        <div class="welcome-industrial">
            <div class="wi-icon">⚙</div>
            <div class="wi-title">设备故障智能诊断</div>
            <div class="wi-desc">
                描述报警代码、异常现象或停机原因<br>
                基于知识库与图谱，生成可执行的排查建议
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dock_pills():
    cols = st.columns(len(QUICK_QUESTION))
    for i, tag in enumerate(QUICK_QUESTION):
        with cols[i]:
            st.markdown('<div class="dock-pill">', unsafe_allow_html=True)
            if st.button(tag, key=f"quick_tag_{i}", width="stretch"):
                st.session_state.pending_prompt = f"{tag}相关故障如何排查？"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


def _submit_feedback(msg: dict, i: int, is_positive: bool, feedback_key: str):
    if st.session_state.get("feedback_in_progress"):
        return
    st.session_state.feedback_in_progress = True
    try:
        user_query = ""
        if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
            user_query = st.session_state.messages[i - 1]["content"]
        send_feedback(
            msg["message_id"], user_query, is_positive,
            st.session_state.session_id, st.session_state.agent_type,
        )
        st.session_state.feedback_given.add(feedback_key)
        st.session_state[f"feedback_type_{feedback_key}"] = "positive" if is_positive else "negative"
        st.rerun()
    finally:
        st.session_state.feedback_in_progress = False


def _render_feedback_buttons(msg: dict, i: int):
    feedback_key = msg.get("message_id", f"msg_{i}")
    if feedback_key in st.session_state.feedback_given:
        ftype = st.session_state.get(f"feedback_type_{feedback_key}", "")
        icon = "👍" if ftype == "positive" else "👎"
        st.caption(f"{icon} 已反馈")
        return
    c1, c2, _ = st.columns([0.05, 0.05, 0.9])
    with c1:
        if st.button("👍", key=f"up_{feedback_key}_{i}"):
            _submit_feedback(msg, i, True, feedback_key)
    with c2:
        if st.button("👎", key=f"down_{feedback_key}_{i}"):
            _submit_feedback(msg, i, False, feedback_key)


def _render_source_references(msg: dict, i: int, raw_content: str):
    source_ids = extract_source_ids(raw_content)
    if msg.get("sources"):
        source_ids = list(dict.fromkeys(source_ids + msg["sources"]))
    display_names = format_source_display_names(source_ids)
    _render_source_expander(display_names, source_ids, key_suffix=str(i))


def _render_assistant_message(msg: dict, i: int):
    raw = msg["content"]
    content = sanitize_answer_text(raw)
    show_thinking = (
        st.session_state.agent_type == "deep_research_agent"
        and st.session_state.get("show_thinking", False)
    )
    if "raw_thinking" in msg and show_thinking:
        _display_thinking_process(msg["raw_thinking"])
        st.markdown(sanitize_answer_text(msg.get("processed_content", content)))
    elif "<think>" in raw and "</think>" in raw:
        think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
        if think_match:
            thinking = think_match.group(1)
            answer_only = raw.replace(f"<think>{thinking}</think>", "").strip()
            if show_thinking:
                _display_thinking_process(thinking)
            st.markdown(sanitize_answer_text(answer_only))
        else:
            st.markdown(sanitize_answer_text(re.sub(r"<think>|</think>", "", raw)))
    else:
        st.markdown(content)
    _render_source_references(msg, i, raw)
    _render_feedback_buttons(msg, i)


def _handle_non_stream_response(api_prompt: str, agent_type: str):
    with st.chat_message("assistant", avatar="🤖"):
        thinking = st.empty()
        thinking.markdown(_thinking_indicator_html("分析中…"), unsafe_allow_html=True)
        try:
            result = chat_qa(
                api_prompt,
                agent_type=agent_type,
                session_id=st.session_state.session_id,
                show_thinking=st.session_state.get("show_thinking", False),
                use_deeper_tool=st.session_state.get("use_deeper_tool", True),
            )
        finally:
            thinking.empty()
        answer = result.get("answer", "抱歉，无法生成回答。")
        display = sanitize_answer_text(answer)
        st.markdown(display)
        sources = collect_source_paths(answer)
        if sources:
            _render_source_expander(sources, extract_source_ids(answer), key_suffix="live_ns")
        if result.get("execution_log"):
            st.session_state.execution_log = result["execution_log"]
        msg_obj = {"role": "assistant", "content": answer, "message_id": str(uuid.uuid4())}
        if sources:
            msg_obj["sources"] = sources
        elif result.get("sources"):
            msg_obj["sources"] = result["sources"]
        st.session_state.messages.append(msg_obj)


def _handle_stream_response(display_prompt: str, api_prompt: str, agent_type: str):
    with st.chat_message("assistant", avatar="🤖"):
        st.session_state.execution_log = [
            f"[检索] Agent: {agent_type}",
            f"[检索] 查询: {display_prompt}",
        ]
        try:
            generator = chat_qa_stream(
                api_prompt,
                agent_type=agent_type,
                session_id=st.session_state.session_id,
                history=_chat_history_for_api(),
            )
            label = "检索中…" if agent_type == "intent_rag_agent" else "思考中…"
            full_response, sources = _stream_assistant_response(generator, label=label)
            if sources:
                _render_source_expander(
                    sources,
                    extract_source_ids(full_response),
                    key_suffix="live_stream",
                )
        except Exception as e:
            full_response = f"生成回答时出错: {e}"
            sources = []
            st.error(full_response)
        if not full_response:
            full_response = "抱歉，未能生成回答。"
        msg = {
            "role": "assistant",
            "content": full_response,
            "message_id": str(uuid.uuid4()),
        }
        if sources:
            msg["sources"] = sources
        st.session_state.messages.append(msg)
        st.session_state.pop("_pending_sources", None)


def _generate_assistant_response(gen: dict):
    display_prompt = gen["display"]
    api_prompt = gen["api"]
    agent_type = gen.get("agent_type", st.session_state.get("agent_type", "general_agent"))
    st.session_state.pop("_stream_partial", None)
    try:
        use_stream = st.session_state.get("use_stream", True) and not st.session_state.debug_mode
        if use_stream:
            _handle_stream_response(display_prompt, api_prompt, agent_type)
        else:
            _handle_non_stream_response(api_prompt, agent_type)
    except Exception as e:
        st.error(f"处理消息时出错: {str(e)}")
        traceback.print_exc()
    finally:
        st.session_state.pop("_gen_assistant", None)
        st.session_state.pop("_stream_partial", None)
        st.session_state.processing_lock = False
    st.rerun()


def _queue_user_message(display_prompt: str):
    if st.session_state.get("processing_lock", False):
        st.warning("请等待当前操作完成…")
        return
    st.session_state.processing_lock = True
    persist_session_agent_type(st.session_state.get("agent_type", "general_agent"))
    st.session_state.messages.append({"role": "user", "content": display_prompt})
    st.session_state._gen_assistant = {
        "display": display_prompt,
        "api": _get_enriched_query(display_prompt),
        "agent_type": st.session_state.get("agent_type", "general_agent"),
    }
    st.rerun()


def display_chat_interface(show_summary_panel: bool = True):
    reconcile_processing_lock()
    st.markdown('<div class="chat-thread-marker"></div>', unsafe_allow_html=True)
    _, main_col, _ = st.columns([1, 7, 1])

    with main_col:
        if not st.session_state.messages:
            _render_welcome()
        else:
            for i, msg in enumerate(st.session_state.messages):
                if msg["role"] == "system" or msg.get("is_summary"):
                    st.markdown(
                        f'<div class="chat-summary-hint">{html.escape(msg["content"])}</div>',
                        unsafe_allow_html=True,
                    )
                    continue
                avatar = "👤" if msg["role"] == "user" else "🤖"
                with st.chat_message(msg["role"], avatar=avatar):
                    if msg["role"] == "assistant":
                        _render_assistant_message(msg, i)
                    else:
                        st.markdown(msg["content"])

        if not st.session_state.messages:
            _render_dock_pills()

        gen = st.session_state.get("_gen_assistant")
        if gen:
            _generate_assistant_response(gen)

    pending = st.session_state.pop("pending_prompt", None)
    chat_prompt = st.chat_input("输入故障现象、报警代码或排查问题…")

    prompt = pending or chat_prompt
    if prompt:
        _queue_user_message(prompt)
