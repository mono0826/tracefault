"""主聊天界面 — 工业风 × 豆包居中对话布局"""

import uuid
import re
import traceback
import streamlit as st

from frontend.common.constants import QUICK_FAULT_TAGS
from frontend.utils.helpers import build_enriched_query, extract_source_ids, sanitize_answer_text
from frontend.utils.api_client import (
    chat_qa,
    chat_qa_stream,
    send_feedback,
    search_sources,
)




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
    cols = st.columns(len(QUICK_FAULT_TAGS))
    for i, tag in enumerate(QUICK_FAULT_TAGS):
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
        source_ids = list(set(source_ids + msg["sources"]))
    if not source_ids:
        return
    with st.expander(f"📎 参考来源 · {len(source_ids)}", expanded=False):
        for sid in source_ids[:8]:
            st.markdown(f'<div class="source-ref-box">{sid}</div>', unsafe_allow_html=True)
        if st.session_state.debug_mode:
            for s_idx, sid in enumerate(source_ids):
                if st.button(f"查看原文 {sid[:12]}…", key=f"src_{sid}_{i}_{s_idx}"):
                    results = search_sources(sid, top_k=1)
                    if results:
                        st.session_state.source_content = results[0]["content"]
                        st.rerun()


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


def _handle_non_stream_response(display_prompt: str, api_prompt: str):
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("分析中…"):
            result = chat_qa(
                api_prompt,
                agent_type=st.session_state.agent_type,
                session_id=st.session_state.session_id,
                show_thinking=st.session_state.get("show_thinking", False),
                use_deeper_tool=st.session_state.get("use_deeper_tool", True),
            )
        answer = result.get("answer", "抱歉，无法生成回答。")
        display = sanitize_answer_text(answer)
        st.markdown(display)
        if result.get("execution_log"):
            st.session_state.execution_log = result["execution_log"]
        msg_obj = {"role": "assistant", "content": answer, "message_id": str(uuid.uuid4())}
        if result.get("sources"):
            msg_obj["sources"] = result["sources"]
        st.session_state.messages.append(msg_obj)


def _handle_stream_response(display_prompt: str, api_prompt: str):
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("检索知识库…"):
            st.session_state.execution_log = [
                f"[检索] Agent: {st.session_state.agent_type}",
                f"[检索] 查询: {display_prompt}",
            ]
        try:
            generator = chat_qa_stream(
                api_prompt,
                agent_type=st.session_state.agent_type,
                session_id=st.session_state.session_id,
            )
            full_response = st.write_stream(generator)
        except Exception as e:
            full_response = f"生成回答时出错: {e}"
            st.error(full_response)
        st.session_state.messages.append({
            "role": "assistant", "content": full_response, "message_id": str(uuid.uuid4()),
        })


def _process_user_message(display_prompt: str):
    if st.session_state.get("processing_lock", False):
        st.warning("请等待当前操作完成…")
        return
    st.session_state.processing_lock = True
    api_prompt = _get_enriched_query(display_prompt)
    with st.chat_message("user", avatar="👤"):
        st.markdown(display_prompt)
    st.session_state.messages.append({"role": "user", "content": display_prompt})
    try:
        use_stream = st.session_state.get("use_stream", True) and not st.session_state.debug_mode
        if use_stream:
            _handle_stream_response(display_prompt, api_prompt)
        else:
            _handle_non_stream_response(display_prompt, api_prompt)
    except Exception as e:
        st.error(f"处理消息时出错: {str(e)}")
        traceback.print_exc()
    finally:
        st.session_state.processing_lock = False
    st.rerun()


def display_chat_interface(show_summary_panel: bool = True):
    _, main_col, _ = st.columns([1, 7, 1])

    with main_col:
        if st.session_state.get("processing_lock", False):
            st.warning("请等待当前操作完成…")

        if not st.session_state.messages:
            _render_welcome()
        else:
            for i, msg in enumerate(st.session_state.messages):
                avatar = "👤" if msg["role"] == "user" else "🤖"
                with st.chat_message(msg["role"], avatar=avatar):
                    if msg["role"] == "assistant":
                        _render_assistant_message(msg, i)
                    else:
                        st.markdown(msg["content"])

    if not st.session_state.messages:
        _, pill_col, _ = st.columns([1, 7, 1])
        with pill_col:
            _render_dock_pills()

    pending = st.session_state.pop("pending_prompt", None)
    chat_prompt = st.chat_input("输入故障现象、报警代码或排查问题…")

    prompt = pending or chat_prompt
    if prompt:
        _process_user_message(prompt)
