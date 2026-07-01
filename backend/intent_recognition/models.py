"""
用户意图识别 — 数据模型定义

定义意图分类和查询改写的结构化数据模型，供上下游模块使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    """用户意图类型"""

    # 设备故障相关查询：问故障现象、原因、维修方案等
    EQUIPMENT_QA = "equipment_qa"
    # 日常对话：打招呼、闲聊、非设备相关问题
    CASUAL_CHAT = "casual_chat"


@dataclass
class IntentResult:
    """意图识别结果"""

    intent: IntentType  # 识别到的意图
    confidence: float  # 置信度 [0, 1]
    explanation: str  # 判断依据简述
    needs_rewrite: bool = False  # 是否需要改写后检索


@dataclass
class RewriteResult:
    """查询改写结果"""

    original_query: str  # 原始用户输入
    rewritten_query: str  # 改写后的主查询（用于检索）
    rewrite_reason: str  # 改写原因
    expansion_terms: list[str] = field(default_factory=list)  # 扩展的关键词
    sub_questions: list[str] = field(default_factory=list)  # 拆分的子问题（无拆分时 = [rewritten_query]）
    should_split: bool = False  # 是否拆分为多个子问题


@dataclass
class TermMapping:
    """术语映射规则"""

    source_term: str  # 来源词（用户输入）
    target_term: str  # 目标词（改写后）
    enabled: bool = True
    priority: int = 0


# 示例 / 可识别的设备故障关键词库（供 prompt 构造参考）
EQUIPMENT_KEYWORDS = [
    "故障", "异常", "损坏", "失效", "报警", "停机",
    "维修", "更换", "调试", "保养", "诊断",
    "温度", "压力", "振动", "噪音", "泄漏", "转速",
    "电机", "轴承", "齿轮", "泵", "阀", "管道", "压缩机",
    "参数", "标准", "范围", "允许值",
]
