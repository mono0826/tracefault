"""前端工具函数"""

import uuid
import re
from pathlib import Path
from typing import List
import streamlit as st

_SUPPORTED_DOC_SUFFIXES = {
    ".txt", ".pdf", ".md", ".docx", ".doc", ".csv", ".json", ".yaml", ".yml",
}


def count_folder_files(folder: str | Path, *, recursive: bool = True) -> int:
    """统计文件夹内可构建的文档文件数（递归子目录）"""
    path = Path(folder)
    if not path.is_dir():
        return 0
    if recursive:
        files = path.rglob("*")
    else:
        files = path.iterdir()
    return sum(
        1 for p in files
        if p.is_file() and p.suffix.lower() in _SUPPORTED_DOC_SUFFIXES
    )


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


def build_enriched_query(user_prompt: str, equipment_type: str = "",
                         equipment_id: str = "", fault_severity: str = "") -> str:
    """将诊断上下文拼接到用户问题（仅在有上下文时生效，不影响纯问答行为）"""
    parts = []
    if equipment_type and equipment_type != "未指定":
        parts.append(f"设备类型: {equipment_type}")
    if equipment_id and equipment_id.strip():
        parts.append(f"设备编号: {equipment_id.strip()}")
    if fault_severity and fault_severity != "未指定":
        parts.append(f"故障等级: {fault_severity}")
    if not parts:
        return user_prompt
    return "【诊断上下文】" + "；".join(parts) + "\n【故障描述】" + user_prompt


def sanitize_answer_text(content: str) -> str:
    """移除回答末尾的原始检索元数据（如 {'data': {'Chunks': [...]}}），保留正文"""
    if not isinstance(content, str) or not content.strip():
        return content or ""

    text = content
    # 移除末尾 data 元数据块（单/双引号、多行）
    text = re.sub(
        r"\n*\{['\"]data['\"]\s*:\s*\{.*?\}\s*\}\s*$",
        "",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\n*\{'data':\s*\{.*?\}\s*\}\s*$",
        "",
        text,
        flags=re.DOTALL,
    )

    cleaned_lines = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("{'data':") or s.startswith('{"data":'):
            continue
        if s.startswith("引用数据") or s.startswith("引用来源"):
            continue
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()
    if not result and content.strip():
        return "暂无有效回答，请尝试换一种描述方式或检查知识库是否已构建。"
    return result


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
