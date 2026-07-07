"""
意图分类器 — 判断用户输入是设备故障相关查询还是日常对话

使用 LLM 对用户 query 进行意图二分类：
  - equipment_qa : 设备故障相关（故障诊断、维修、参数等）
  - casual_chat  : 日常对话（打招呼、闲聊、非技术问题）
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, List

from backend.models.get_models import get_llm_model
from backend.intent_recognition.models import IntentType, IntentResult

# === 从独立文件加载系统提示词 ===

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_INTENT_CLASSIFIER_PROMPT_PATH = _PROMPT_DIR / "intent_classifier.st"

INTENT_SYSTEM_PROMPT = (
    _INTENT_CLASSIFIER_PROMPT_PATH.read_text(encoding="utf-8")
    if _INTENT_CLASSIFIER_PROMPT_PATH.exists()
    else ""
)


def _format_history(history: Optional[List[dict]]) -> str:
    """将历史消息列表格式化为文本"""
    if not history:
        return ""
    lines = []
    for m in history:
        role = "用户" if m.get("role") == "user" else "助手"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def classify_intent(
    query: str,
    history: Optional[List[dict]] = None,
    llm=None,
) -> IntentResult:
    """
    对用户 query 进行意图分类（考虑历史上下文）。

    Args:
        query: 用户输入文本
        history: 可选的历史消息列表
        llm: 可选的 LLM 实例，不传则自动创建

    Returns:
        IntentResult: 分类结果
    """
    if not query or not query.strip():
        return IntentResult(
            intent=IntentType.CASUAL_CHAT,
            confidence=1.0,
            explanation="空输入，视为日常对话",
            needs_rewrite=False,
        )

    _llm = llm or get_llm_model()

    # 构建带上下文的输入
    user_input = f"用户输入：{query.strip()}"
    history_text = _format_history(history)
    if history_text:
        user_input = f"对话历史：\n{history_text}\n\n{user_input}"

    try:
        resp = _llm.invoke([
            ("system", INTENT_SYSTEM_PROMPT),
            ("human", user_input),
        ])
        content = resp.content.strip()
        # 提取 JSON（防止 LLM 额外输出）
        json_str = _extract_json(content)
        data = json.loads(json_str)
        intent = IntentType(data["intent"])
        return IntentResult(
            intent=intent,
            confidence=float(data["confidence"]),
            explanation=data.get("explanation", ""),
            needs_rewrite=bool(data.get("needs_rewrite", False)),
        )
    except Exception as e:
        # 解析失败时降级：根据关键词做简单规则分类
        return _fallback_classify(query)


def _extract_json(text: str) -> str:
    """从 LLM 输出中提取第一个 JSON 对象"""
    # 尝试直接解析
    text = text.strip()
    if text.startswith("{"):
        return text
    # 尝试从 ```json ... ``` 中提取
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # 尝试找第一个 { 到最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    raise ValueError(f"无法从输出中提取 JSON: {text[:200]}")


def _fallback_classify(query: str) -> IntentResult:
    """LLM 调用失败时的规则兜底分类"""
    from backend.intent_recognition.models import EQUIPMENT_KEYWORDS

    q = query.lower()
    # 检查是否包含设备故障关键词
    matched = [kw for kw in EQUIPMENT_KEYWORDS if kw in q]

    if matched:
        return IntentResult(
            intent=IntentType.EQUIPMENT_QA,
            confidence=0.6,
            explanation=f"规则兜底：命中关键词 {matched[:3]}",
            needs_rewrite=len(matched) <= 1,
        )

    # 简单问候语
    greetings = {"你好", "您好", "hello", "hi", "在吗", "早上好", "下午好", "谢谢", "再见"}
    if q.strip() in greetings or any(g in q for g in {"你好", "您好", "hello"}):
        return IntentResult(
            intent=IntentType.CASUAL_CHAT,
            confidence=0.8,
            explanation="规则兜底：匹配到问候语",
            needs_rewrite=False,
        )

    # 默认保守处理：当作设备相关，让下游检索决定
    return IntentResult(
        intent=IntentType.EQUIPMENT_QA,
        confidence=0.5,
        explanation="规则兜底：无法明确判断，默认走检索",
        needs_rewrite=True,
    )
