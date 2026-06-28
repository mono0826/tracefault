"""前端工具函数"""

import uuid
import re
from typing import List
import streamlit as st


def generate_session_id() -> str:
    """生成对话会话 ID"""
    return uuid.uuid4().hex[:16]


def extract_source_ids(answer: str) -> List[str]:
    """从回答中提取引用的源 ID"""
    source_ids = []

    # 提取 Chunk IDs (兼容旧格式)
    chunks_pattern = r"Chunks':\s*\[([^\]]*)\]"
    matches = re.findall(chunks_pattern, answer)

    for match in matches:
        quoted_ids = re.findall(r"'([^']*)'", match)
        if quoted_ids:
            source_ids.extend(quoted_ids)
        else:
            ids = [id.strip() for id in match.split(",") if id.strip()]
            source_ids.extend(ids)

    return list(set(source_ids))


def display_source_content(content: str):
    """更好地显示源内容"""
    st.markdown("""
    <style>
    .source-content {
        white-space: pre-wrap;
        overflow-x: auto;
        font-family: monospace;
        line-height: 1.6;
        background-color: #f5f5f5;
        border-radius: 5px;
        padding: 15px;
        max-height: 600px;
        overflow-y: auto;
        border: 1px solid #e1e4e8;
        color: #24292e;
    }
    </style>
    """, unsafe_allow_html=True)

    formatted = content.replace("\n", "<br>")
    st.markdown(f'<div class="source-content">{formatted}</div>', unsafe_allow_html=True)


def process_thinking_content(content: str, show_thinking: bool = False) -> dict:
    """处理带有 <think> 标签的思考过程内容"""
    if not isinstance(content, str):
        return {"processed": content, "has_thinking": False}

    if "<think>" in content and "</think>" in content:
        think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            answer_only = content.replace(f"<think>{thinking}</think>", "").strip()
            quoted = "\n".join(f"> {line}" for line in thinking.split("\n"))

            return {
                "processed": answer_only,
                "has_thinking": True,
                "thinking": quoted,
                "original": content,
            }

    return {"processed": content, "has_thinking": False}
