"""前端工具函数"""

import ast
import uuid
import re
from pathlib import Path
from typing import List, Optional, Tuple
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


def _matching_brace_end(text: str, start: int) -> Optional[int]:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _find_data_dict_span(text: str) -> Optional[Tuple[int, int]]:
    for pattern in (r"\{'data'\s*:", r'\{"data"\s*:'):
        match = re.search(pattern, text)
        if not match:
            continue
        brace = text.find("{", match.start())
        end = _matching_brace_end(text, brace)
        if end:
            return brace, end
    return None


def _parse_citation_data_block(block: str) -> List[str]:
    names: List[str] = []
    try:
        obj = ast.literal_eval(block)
        chunks = obj.get("data", {}).get("Chunks", []) if isinstance(obj, dict) else []
        for chunk in chunks:
            if isinstance(chunk, dict):
                fn = chunk.get("file_name") or chunk.get("fileName")
                if fn:
                    names.append(str(fn))
    except (ValueError, SyntaxError, TypeError):
        pass
    return names


_INLINE_CITATION_BLOCK_RE = re.compile(
    r"\[(?:Entities|Chunks|Relationships|Reports)\s*:[^\]]*\]",
    re.IGNORECASE,
)
_INLINE_CITATION_START_RE = re.compile(
    r"\[(?:Entities|Chunks|Relationships|Reports)\s*:",
    re.IGNORECASE,
)
_FILE_NAME_VALUE_RE = re.compile(
    r"""file_name\s*[:=]\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def _strip_inline_citation_blocks(text: str) -> str:
    """移除 [Entities: ...] / [Relationships: ...] 等内联引用块"""
    text = _INLINE_CITATION_BLOCK_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_source_ids(answer: str) -> List[str]:
    """从回答中提取引用文件的文件名（去重，保留顺序）"""
    if not isinstance(answer, str) or not answer.strip():
        return []

    seen = set()
    source_ids: List[str] = []

    def add_name(name: str):
        name = name.strip()
        norm = Path(name.replace("\\", "/")).as_posix()
        if norm and norm not in seen:
            seen.add(norm)
            source_ids.append(name)

    for fn in _FILE_NAME_VALUE_RE.findall(answer):
        add_name(fn)

    text = answer
    while True:
        span = _find_data_dict_span(text)
        if not span:
            break
        block = text[span[0]:span[1]]
        for fn in _parse_citation_data_block(block):
            add_name(fn)
        text = text[:span[0]] + text[span[1]:]

    return source_ids


def format_source_display_names(source_ids: List[str]) -> List[str]:
    """引用来源展示名：保留完整路径，去重"""
    seen = set()
    names: List[str] = []
    for sid in source_ids:
        raw = sid.strip()
        if not raw:
            continue
        norm = Path(raw.replace("\\", "/")).as_posix()
        if norm in seen:
            continue
        seen.add(norm)
        names.append(raw)
    return names


def _citation_start_index(text: str) -> Optional[int]:
    """定位引用元数据块的起始位置"""
    patterns = (
        r"#{1,6}\s*引用(?:数据|来源)",
        r"\*\*引用(?:数据|来源)\*\*",
        r"\{'data'\s*:",
        r'\{"data"\s*:',
        r"\[(?:Entities|Chunks|Relationships|Reports)\s*:",
    )
    earliest: Optional[int] = None
    for pat in patterns:
        match = re.search(pat, text)
        if match and (earliest is None or match.start() < earliest):
            earliest = match.start()
    return earliest


def truncate_before_citation(text: str) -> str:
    """截断首个未闭合引用块之后的内容（流式尾部保护）"""
    if not text:
        return text
    idx = _citation_start_index(text)
    if idx is None:
        return text
    return text[:idx].rstrip()


def _has_incomplete_citation_tail(text: str) -> bool:
    """末尾是否存在尚未闭合的引用块"""
    idx = _citation_start_index(text)
    if idx is None:
        return False
    tail = text[idx:]
    if _INLINE_CITATION_START_RE.match(tail):
        return _INLINE_CITATION_BLOCK_RE.match(tail) is None
    brace = text.find("{", idx)
    if brace >= 0:
        return _matching_brace_end(text, brace) is None
    return True


def format_stream_body(content: str) -> str:
    """流式展示正文：移除已完成的引用块，隐藏未闭合的引用尾部"""
    if not content:
        return content
    if _has_incomplete_citation_tail(content):
        content = truncate_before_citation(content)
    return _strip_citation_raw_content(content)


def collect_source_paths(content: str) -> List[str]:
    """从完整回答中提取引用文件路径（去重）"""
    return format_source_display_names(extract_source_ids(content))


def _strip_citation_raw_content(text: str) -> str:
    text = re.sub(r"#{1,6}\s*引用(?:数据|来源)\s*\n?", "", text)
    text = re.sub(r"\*\*引用(?:数据|来源)\*\*\s*\n?", "", text)

    while True:
        span = _find_data_dict_span(text)
        if not span:
            break
        start, end = span
        text = text[:start].rstrip() + "\n" + text[end:].lstrip()

    text = _strip_inline_citation_blocks(text)

    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{'data':") or stripped.startswith('{"data":'):
            continue
        if re.match(r"引用(?:数据|来源)", stripped):
            continue
        if _INLINE_CITATION_START_RE.search(stripped):
            continue
        if "'Entities'" in stripped or '"Entities"' in stripped:
            if "'Chunks'" in stripped or '"Chunks"' in stripped or "Reports" in stripped:
                continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def sanitize_answer_text(content: str) -> str:
    """移除原始引用元数据；文件名由「参考来源」折叠面板展示"""
    if not isinstance(content, str) or not content.strip():
        return content or ""

    text = _strip_citation_raw_content(content)

    if not text.strip() and content.strip():
        return "暂无有效回答，请尝试换一种描述方式或检查知识库是否已构建。"
    return text.strip()


def format_answer_for_display(content: str, *, streaming: bool = False) -> str:
    """展示用文本：流式阶段仅正文，完成后剥离全部引用元数据"""
    if not isinstance(content, str) or not content.strip():
        return content or ""
    if streaming:
        return format_stream_body(content)
    return sanitize_answer_text(content)


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
