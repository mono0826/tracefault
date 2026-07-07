"""
意图识别 + 查询改写 管道

处理流程：
    用户 query
      → Layer 1: 术语归一化 (term_mapping)
      → Layer 2: 意图分类 (classify_intent)
      → Layer 3: 查询改写+拆分 (rewrite_query)
      → 输出结构化结果

用法：
    from backend.intent_recognition.main import process_query

    result = process_query("那个轴承还能用吗？", history=[...])
    print(result["rewritten_query"])   # 改写后用于检索的 query
    print(result["intent"])            # 意图类型
"""

from __future__ import annotations

import time
from typing import Optional

from backend.models.get_models import get_llm_model
from backend.intent_recognition import (
    IntentType,
    classify_intent,
    rewrite_query,
    rewrite_with_context,
    get_term_mapping_service,
)


def process_query(
    query: str,
    history: Optional[list[dict]] = None,
    llm=None,
    verbose: bool = True,
) -> dict:
    """
    对用户 query 做意图识别 + 改写，输出结构化结果供下游使用。

    Args:
        query: 用户输入文本
        history: 可选的历史消息列表
        llm: 可选的 LLM 实例
        verbose: 是否打印处理过程日志

    Returns:
        dict: {
            "original_query": str,     # 原始输入
            "normalized_query": str,   # 规则归一化后的 query
            "intent": str,             # equipment_qa / casual_chat
            "confidence": float,       # 意图置信度
            "needs_rewrite": bool,     # 是否需要改写
            "rewritten_query": str,    # 改写后的最终 query（供下游检索用）
            "sub_questions": list,     # 拆分的子问题
            "should_split": bool,      # 是否拆分为多子问题
            "expansion_terms": list,   # 扩展关键词
            "pipeline_log": list,      # 处理日志
            "latency_ms": float,       # 总耗时
        }
    """
    start_time = time.time()
    log: list[str] = []
    _llm = llm or get_llm_model()

    def _log(msg: str):
        log.append(msg)
        if verbose:
            print(f"  [{len(log)}] {msg}")

    # ---------------------------------------------------------------
    # 空输入检查
    # ---------------------------------------------------------------
    if not query or not query.strip():
        elapsed = (time.time() - start_time) * 1000
        return {
            "original_query": query or "",
            "normalized_query": query or "",
            "intent": "casual_chat",
            "confidence": 1.0,
            "needs_rewrite": False,
            "rewritten_query": query or "",
            "sub_questions": [],
            "should_split": False,
            "expansion_terms": [],
            "pipeline_log": log,
            "latency_ms": elapsed,
        }

    _log(f"输入: {query}")
    print(f"[意图识别] 输入: {query}")

    # ---------------------------------------------------------------
    # Layer 1: 规则术语归一化
    # ---------------------------------------------------------------
    service = get_term_mapping_service()
    normalized = service.normalize(query)
    if normalized != query:
        _log(f"术语归一化: {query} → {normalized}")
    else:
        _log("术语归一化: 无变化")
    print(f"[意图识别] 术语归一化: {query} → {normalized}")
    # ---------------------------------------------------------------
    # Layer 2: 意图分类（带历史上下文）
    # ---------------------------------------------------------------
    intent = classify_intent(normalized, history=history, llm=_llm)
    print(f"[意图识别] 意图分类: {intent.intent} (置信度={intent.confidence:.2f})")
    # 闲聊意图标记，不需要改写
    if intent.intent == IntentType.CASUAL_CHAT:
        _log(f"意图分类: casual_chat (置信度={intent.confidence:.2f})")
        _log("闲聊意图，跳过改写")
        elapsed = (time.time() - start_time) * 1000
        return {
            "original_query": query,
            "normalized_query": normalized,
            "intent": "casual_chat",
            "confidence": intent.confidence,
            "needs_rewrite": False,
            "rewritten_query": query,
            "sub_questions": [query],
            "should_split": False,
            "expansion_terms": [],
            "pipeline_log": log,
            "latency_ms": elapsed,
        }

    _log(
        f"意图分类: equipment_qa "
        f"(置信度={intent.confidence:.2f}, "
        f"需改写={intent.needs_rewrite})"
    )

    # ---------------------------------------------------------------
    # Layer 3: 查询改写
    # ---------------------------------------------------------------
    if intent.needs_rewrite and history:
        rewrite_result = rewrite_with_context(query, history=history, llm=_llm)
        _log("改写模式: 带上下文")
    elif intent.needs_rewrite:
        rewrite_result = rewrite_query(query, llm=_llm)
        _log("改写模式: 无上下文")
    else:
        rewrite_result = None
        _log("改写模式: 无需改写，使用原始 query")

    final_query = (
        rewrite_result.rewritten_query if rewrite_result else query
    )
    sub_questions = (
        rewrite_result.sub_questions if rewrite_result else [query]
    )
    expansion_terms = (
        rewrite_result.expansion_terms if rewrite_result else []
    )

    _log(f"改写结果: {final_query}")
    if expansion_terms:
        _log(f"扩展词: {', '.join(expansion_terms)}")
    if rewrite_result and rewrite_result.should_split:
        _log(f"多问句拆分: {sub_questions}")

    elapsed = (time.time() - start_time) * 1000
    _log(f"总耗时: {elapsed:.0f}ms")

    return {
        "original_query": query,
        "normalized_query": normalized,
        "intent": "equipment_qa",
        "confidence": intent.confidence,
        "needs_rewrite": intent.needs_rewrite,
        "rewritten_query": final_query,
        "sub_questions": sub_questions,
        "should_split": rewrite_result.should_split if rewrite_result else False,
        "expansion_terms": expansion_terms,
        "pipeline_log": log,
        "latency_ms": elapsed,
    }


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("请输入 query: ").strip()
    print()
    print("=" * 60)
    result = process_query(query, verbose=True)
    print("=" * 60)
    print()
    if result["intent"] == "casual_chat":
        print(f"意图: 闲聊 (置信度={result['confidence']:.2f})")
        print("无需检索，直接返回友好提示即可")
    else:
        print("意图: 设备故障查询")
        print(f"改写前: {result['normalized_query']}")
        print(f"改写后: {result['rewritten_query']}")
        if result["sub_questions"]:
            print(f"子问题: {result['sub_questions']}")
        if result["expansion_terms"]:
            print(f"扩展词: {result['expansion_terms']}")
