"""主聊天界面组件"""

import uuid
import re
import traceback
import streamlit as st

from frontend.utils.api_client import (
    chat_qa,
    chat_qa_stream,
    send_feedback,
    search_sources,
)


# =============================================================
#  内部辅助
# =============================================================

def _reset_processing_lock():
    st.session_state.processing_lock = False


def _clear_and_rerun():
    """清空聊天并重置锁"""
    st.session_state.processing_lock = False
    st.session_state.messages = []
    st.session_state.execution_log = []
    st.session_state.source_content = None
    st.rerun()


def _display_thinking_process(raw_thinking: str):
    """以引用格式显示深度研究的思考过程"""
    lines = raw_thinking.split("\n")
    quoted = "\n".join(f"> {line}" for line in lines)
    st.markdown(quoted)
    st.markdown("\n\n")


def _get_message_tooltip(agent_type: str) -> str:
    tips = {
        "naive_rag_agent": "【标准 RAG】基于知识库直接检索回答",
        "local_search_agent": "【知识图谱搜索】基于图谱实体和关系检索回答",
    }
    return tips.get(agent_type, "")


# =============================================================
#  消息渲染
# =============================================================

def _render_feedback_buttons(msg: dict, i: int):
    """为助手消息渲染点赞/点踩按钮"""
    feedback_key = msg.get("message_id", f"msg_{i}")

    if feedback_key in st.session_state.feedback_given:
        ftype = st.session_state.get(f"feedback_type_{feedback_key}", "")
        if ftype == "positive":
            st.success("您已对此回答给予肯定！", icon="👍")
        elif ftype == "negative":
            st.error("您已对此回答提出改进建议。", icon="👎")
        else:
            st.info("已收到您的反馈。")
        return

    feedback_container = st.empty()
    col1, col2, _ = st.columns([0.1, 0.1, 0.8])

    with col1:
        if st.button("👍", key=f"up_{feedback_key}_{i}"):
            if st.session_state.get("feedback_in_progress", False):
                feedback_container.warning("请等待当前操作完成...")
            else:
                st.session_state.feedback_in_progress = True
                try:
                    user_query = ""
                    if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
                        user_query = st.session_state.messages[i - 1]["content"]

                    with feedback_container, st.spinner("提交反馈..."):
                        resp = send_feedback(
                            msg["message_id"], user_query, True,
                            st.session_state.session_id, st.session_state.agent_type,
                        )

                    st.session_state.feedback_given.add(feedback_key)
                    st.session_state[f"feedback_type_{feedback_key}"] = "positive"

                    action = resp.get("action", "")
                    if "高质量" in action:
                        feedback_container.success("感谢您的肯定！此回答已被标记为高质量。", icon="🙂")
                    else:
                        feedback_container.success("感谢您的反馈！", icon="👍")
                except Exception as e:
                    feedback_container.error(f"提交反馈时出错: {e}")
                finally:
                    st.session_state.feedback_in_progress = False

    with col2:
        if st.button("👎", key=f"down_{feedback_key}_{i}"):
            if st.session_state.get("feedback_in_progress", False):
                feedback_container.warning("请等待当前操作完成...")
            else:
                st.session_state.feedback_in_progress = True
                try:
                    user_query = ""
                    if i > 0 and st.session_state.messages[i - 1]["role"] == "user":
                        user_query = st.session_state.messages[i - 1]["content"]

                    with feedback_container, st.spinner("提交反馈..."):
                        resp = send_feedback(
                            msg["message_id"], user_query, False,
                            st.session_state.session_id, st.session_state.agent_type,
                        )

                    st.session_state.feedback_given.add(feedback_key)
                    st.session_state[f"feedback_type_{feedback_key}"] = "negative"

                    action = resp.get("action", "")
                    if "清除" in action:
                        feedback_container.error("已收到您的反馈，此回答将不再使用。", icon="🔄")
                    else:
                        feedback_container.error("已收到您的反馈，我们会改进。", icon="👎")
                except Exception as e:
                    feedback_container.error(f"提交反馈时出错: {e}")
                finally:
                    st.session_state.feedback_in_progress = False


def _render_source_references(msg: dict, i: int):
    """在调试模式下渲染源内容引用按钮"""
    if not st.session_state.debug_mode:
        return

    from frontend.utils.helpers import extract_source_ids
    source_ids = extract_source_ids(msg["content"])
    if not source_ids:
        return

    with st.expander("📎 查看引用源文本", expanded=False):
        for s_idx, sid in enumerate(source_ids):
            btn_key = f"src_{sid}_{i}_{s_idx}"
            if st.button(f"加载 {sid}", key=btn_key):
                with st.spinner("加载源文本..."):
                    results = search_sources(sid, top_k=1)
                    if results:
                        st.session_state.source_content = results[0]["content"]
                        st.rerun()


# =============================================================
#  消息发送 & 流式处理
# =============================================================

def _handle_non_stream_response(prompt: str):
    """非流式模式：调用 chat_qa 并更新状态"""
    with st.chat_message("assistant"):
        tooltip = _get_message_tooltip(st.session_state.agent_type)
        if tooltip:
            st.caption(tooltip)

        with st.spinner("思考中..."):
            result = chat_qa(
                prompt,
                agent_type=st.session_state.agent_type,
                session_id=st.session_state.session_id,
                show_thinking=st.session_state.get("show_thinking", False),
                use_deeper_tool=st.session_state.get("use_deeper_tool", True),
            )

        answer = result.get("answer", "抱歉，无法生成回答。")

        # 显示思考过程
        raw_thinking = result.get("raw_thinking", "")
        if raw_thinking and st.session_state.get("show_thinking", False):
            _display_thinking_process(raw_thinking)

        st.markdown(answer)

        # 保存执行日志
        if result.get("execution_log"):
            st.session_state.execution_log = result["execution_log"]

        # 构造消息对象
        msg_obj = {
            "role": "assistant",
            "content": answer,
            "message_id": str(uuid.uuid4()),
        }
        if raw_thinking:
            msg_obj["raw_thinking"] = raw_thinking
            msg_obj["processed_content"] = answer

        st.session_state.messages.append(msg_obj)


def _handle_stream_response(prompt: str):
    """流式模式：先搜索（spinner），再流式输出"""
    with st.chat_message("assistant"):
        tooltip = _get_message_tooltip(st.session_state.agent_type)
        if tooltip:
            st.caption(tooltip)

        # 1. 搜索阶段（spinner）
        with st.spinner("正在搜索知识库..."):
            try:
                st.session_state.execution_log = [
                    f"[检索] Agent类型: {st.session_state.agent_type}",
                    f"[检索] 用户查询: {prompt}",
                ]
            except Exception as e:
                st.session_state.execution_log = [f"[检索] 检索出错: {e}"]

        # 2. 流式生成阶段
        try:
            generator = chat_qa_stream(
                prompt,
                agent_type=st.session_state.agent_type,
                session_id=st.session_state.session_id,
                show_thinking=st.session_state.get("show_thinking", False),
                use_deeper_tool=st.session_state.get("use_deeper_tool", True),
            )

            full_response = st.write_stream(generator)
        except Exception as e:
            full_response = f"生成回答时出错: {e}"
            st.error(full_response)

        # 保存消息
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "message_id": str(uuid.uuid4()),
        })


# =============================================================
#  主界面
# =============================================================

def display_chat_interface():
    """显示主聊天界面"""
    # 标题
    st.title("💬 智能问答")
    st.caption("企业设备故障智能诊断助手 — 输入设备故障描述，获取诊断建议")

    # ---------- 控制栏 ----------
    cols = st.columns([3, 1, 1])
    with cols[0]:
        agent_type = st.selectbox(
            "选择 Agent 类型",
            options=["naive_rag_agent", "local_search_agent"],
            format_func=lambda x: {
                "naive_rag_agent": "标准 RAG",
                "local_search_agent": "知识图谱搜索",
            }[x],
            key="header_agent_type",
            help="naive_rag_agent: 基础检索+生成 | local_search_agent: 知识图谱局部搜索",
        )
        if agent_type != st.session_state.agent_type:
            st.session_state.agent_type = agent_type
            _reset_processing_lock()

    with cols[1]:
        if not st.session_state.debug_mode:
            use_stream = st.checkbox(
                "流式响应",
                value=st.session_state.get("use_stream", True),
                key="header_use_stream",
                help="实时显示生成结果",
            )
            st.session_state.use_stream = use_stream
        else:
            st.session_state.use_stream = False
            st.info("调试模式已禁用流式")

    with cols[2]:
        st.button("🗑️ 清除聊天", on_click=_clear_and_rerun)

    st.markdown("---")

    # ---------- 处理锁 ----------
    if st.session_state.get("processing_lock", False):
        st.warning("请等待当前操作完成...")
        if st.button("强制重置处理状态", key="force_reset"):
            st.session_state.processing_lock = False
            st.rerun()

    # ---------- 消息历史 ----------
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            content = msg["content"]

            # 助手消息特殊处理
            if msg["role"] == "assistant":
                # 思考过程
                show_thinking = (
                    st.session_state.agent_type == "deep_research_agent"
                    and st.session_state.get("show_thinking", False)
                )

                if "raw_thinking" in msg and show_thinking:
                    _display_thinking_process(msg["raw_thinking"])
                    st.markdown(msg.get("processed_content", content))
                elif "<think>" in content and "</think>" in content:
                    think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
                    if think_match:
                        thinking = think_match.group(1)
                        answer_only = content.replace(f"<think>{thinking}</think>", "").strip()
                        if show_thinking:
                            _display_thinking_process(thinking)
                        st.markdown(answer_only)
                    else:
                        st.markdown(re.sub(r"<think>|</think>", "", content))
                else:
                    st.markdown(content)

                # 反馈按钮
                _render_feedback_buttons(msg, i)

                # 源内容（调试模式）
                _render_source_references(msg, i)

            else:
                st.markdown(content)

    # ---------- 输入 ----------
    if prompt := st.chat_input("描述设备故障现象..."):
        if st.session_state.get("processing_lock", False):
            st.warning("请等待当前操作完成...")
            st.stop()

        st.session_state.processing_lock = True

        # 用户消息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        try:
            use_stream = st.session_state.get("use_stream", True) and not st.session_state.debug_mode

            if use_stream:
                _handle_stream_response(prompt)
            else:
                _handle_non_stream_response(prompt)

        except Exception as e:
            st.error(f"处理消息时出错: {str(e)}")
            traceback.print_exc()
        finally:
            st.session_state.processing_lock = False

        st.rerun()
