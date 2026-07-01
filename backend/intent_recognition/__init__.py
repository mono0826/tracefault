"""
用户意图识别模块 — 查询改写 + 意图分类

提供两个核心能力：
  1. intent_classifier  : 判断用户输入是设备故障相关还是日常对话
  2. query_rewriter     : 三层递进改写（规则归一化 → LLM改写+拆分 → 规则拆分兜底）

使用方式：
    from backend.intent_recognition import classify_intent, rewrite_query

    intent = classify_intent("这个轴承温度多少算正常？")
    rewritten = rewrite_query("它为什么震动这么大？")
"""

from backend.intent_recognition.models import (
    IntentType,
    IntentResult,
    RewriteResult,
    TermMapping,
)
from backend.intent_recognition.intent_classifier import classify_intent
from backend.intent_recognition.query_rewriter import (
    rewrite_query,
    rewrite_with_context,
)
from backend.intent_recognition.term_mapping import (
    QueryTermMappingService,
    get_term_mapping_service,
)

__all__ = [
    # 数据模型
    "IntentType",
    "IntentResult",
    "RewriteResult",
    "TermMapping",
    # 意图分类
    "classify_intent",
    # 查询改写
    "rewrite_query",
    "rewrite_with_context",
    # 术语归一化
    "QueryTermMappingService",
    "get_term_mapping_service",
]
