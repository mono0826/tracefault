"""
查询改写器 — 三层递进改写策略

对标 ragent/bootstrap 的 MultiQuestionRewriteService：

    Layer 1 (规则归一化) →  Layer 2 (LLM 改写+拆分)  →  Layer 3 (规则拆分兜底)
    QueryTermMapping       rewrite_with_split()          ruleBasedSplit()

完整流程：
    normalize(query)
        → 如果改写开关关闭：返回 normalized + ruleBasedSplit
        → 否则：LLM 改写+拆分
            → 如果 LLM 成功：返回结果
            → 如果 LLM 失败：返回 normalized + ruleBasedSplit(兜底)

历史感知：rewrite_with_context() 会传入最近 2 轮对话用于指代消解。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Optional

from backend.models.get_models import get_llm_model
from backend.intent_recognition.models import RewriteResult
from backend.intent_recognition.term_mapping import get_term_mapping_service

# ============================================================
# 配置开关
# ============================================================

# 是否启用 LLM 改写（可通过环境变量控制）
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)

# ============================================================
# Prompt 加载
# ============================================================

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    """从 prompts 目录加载 prompt 模板"""
    path = _PROMPT_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


REWRITE_SYSTEM_PROMPT = _load_prompt("query_rewrite.st")

# ============================================================
# Layer 1: 规则归一化
# ============================================================


def _normalize(text: str) -> str:
    """规则术语归一化（同义词、缩写映射）"""
    service = get_term_mapping_service()
    return service.normalize(text)


# ============================================================
# Layer 2: LLM 改写 + 多问句拆分
# ============================================================


def _llm_rewrite_and_split(
    question: str,
    history: Optional[List[dict]] = None,
    llm=None,
) -> Optional[RewriteResult]:
    """
    调用 LLM 进行改写+拆分。
    返回 None 表示 LLM 调用/解析失败，由调用方兜底。
    """
    if not REWRITE_SYSTEM_PROMPT:
        return None

    _llm = llm or get_llm_model()

    # 构建历史上下文
    history_text = _format_history(history) if history else ""
    user_content = question
    if history_text:
        user_content = f"## 聊天历史\n{history_text}\n\n## 当前问题\n{question}"

    try:
        resp = _llm.invoke([
            ("system", REWRITE_SYSTEM_PROMPT),
            ("human", user_content),
        ])
        data = _parse_rewrite_response(resp.content)
        if data is None:
            return None

        rewrite = (data.get("rewrite") or "").strip()
        print(f"LLM 改写结果: {rewrite}")
        if not rewrite:
            return None

        sub_questions = data.get("sub_questions", [])
        should_split = data.get("should_split", False)

        # 一致性约束：若不拆分，sub_questions 应与 rewrite 一致
        if not should_split or not sub_questions:
            sub_questions = [rewrite]

        return RewriteResult(
            original_query=question,
            rewritten_query=rewrite,
            rewrite_reason=data.get("reason", ""),
            expansion_terms=data.get("expansion_terms", []),
            sub_questions=sub_questions,
            should_split=should_split,
        )
    except Exception:
        return None


# ============================================================
# Layer 3: 规则拆分兜底
# ============================================================


def _rule_based_split(text: str) -> List[str]:
    """按常见分隔符拆分多问句（兜底策略）"""
    parts = re.split(r"[?？。；;！!\n]+", text)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return [text]
    # 补回问号
    return [p if p.endswith(("？", "?")) else p + "？" for p in parts]


# ============================================================
# 对外接口
# ============================================================


def rewrite_query(
    query: str,
    llm=None,
) -> RewriteResult:
    """
    改写用户 query，提升检索召回率。

    流程：
        1. 规则归一化 (term_mapping)
        2. LLM 改写+拆分（开关打开时）
        3. LLM 失败 → 规则拆分兜底

    Args:
        query: 用户输入
        llm: 可选的 LLM 实例

    Returns:
        RewriteResult: 改写结果
    """
    if not query or not query.strip():
        return RewriteResult(
            original_query=query or "",
            rewritten_query=query or "",
            rewrite_reason="空查询，无需改写",
            sub_questions=[],
        )

    # Layer 1: 规则归一化
    normalized = _normalize(query)

    # Layer 2: LLM 改写+拆分
    if QUERY_REWRITE_ENABLED and REWRITE_SYSTEM_PROMPT:
        result = _llm_rewrite_and_split(normalized, llm=llm)
        if result is not None:
            return result

    # Layer 3: 兜底 — 返回归一化结果 + 规则拆分
    subs = _rule_based_split(normalized)
    return RewriteResult(
        original_query=query,
        rewritten_query=normalized,
        rewrite_reason="LLM改写未启用或失败，使用规则归一化结果",
        sub_questions=subs,
        should_split=len(subs) > 1,
    )


def rewrite_with_context(
    query: str,
    history: Optional[List[dict]] = None,
    llm=None,
) -> RewriteResult:
    """
    结合聊天历史改写 query（指代消解 + 上下文融合）。

    Args:
        query: 用户最新输入
        history: 历史消息列表，每项为 {"role": "user"/"assistant", "content": str}
        llm: 可选的 LLM 实例

    Returns:
        RewriteResult: 改写结果
    """
    if not query or not query.strip():
        return RewriteResult(
            original_query=query or "",
            rewritten_query=query or "",
            rewrite_reason="空查询，无需改写",
            sub_questions=[],
        )

    # Layer 1: 规则归一化
    normalized = _normalize(query)

    # Layer 2: LLM 改写+拆分（带历史）
    if QUERY_REWRITE_ENABLED and REWRITE_SYSTEM_PROMPT:
        result = _llm_rewrite_and_split(normalized, history=history, llm=llm)
        if result is not None:
            return result

    # Layer 3: 兜底
    subs = _rule_based_split(normalized)
    return RewriteResult(
        original_query=query,
        rewritten_query=normalized,
        rewrite_reason="上下文改写未启用或失败，使用规则归一化结果",
        sub_questions=subs,
        should_split=len(subs) > 1,
    )


# ============================================================
# 内部工具
# ============================================================


def _parse_rewrite_response(content: str) -> Optional[dict]:
    """从 LLM 响应中解析 JSON"""
    text = content.strip()
    # 移除可能的 markdown 代码块标记
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 找第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _format_history(history: List[dict], max_rounds: int = 2) -> str:
    """格式化聊天历史为文本（只保留最近 max_rounds 轮）"""
    lines = []
    for msg in history[-max_rounds * 2 :]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prefix = "用户" if role == "user" else "助手"
        lines.append(f"{prefix}：{content[:200]}")
    return "\n".join(lines)
