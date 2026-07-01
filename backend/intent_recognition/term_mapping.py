"""
术语归一化 — 规则化同义词/缩写映射（Layer 1）

对标 ragent/bootstrap 的 QueryTermMappingService，用可配置的
规则表做低成本的术语归一化，不依赖 LLM。

用法：
    service = QueryTermMappingService()
    text = service.normalize("电机温升过高")
    # → "电机温度升高过高"（如果配置了 温升→温度升高）
"""

from __future__ import annotations

import re
from typing import List, Optional

from backend.intent_recognition.models import TermMapping

# ============================================================
# 默认映射规则（可扩展，也可从数据库/配置文件加载）
# ============================================================

DEFAULT_MAPPINGS: list[TermMapping] = [
    # ---- 设备/部件简称 → 全称 ----
    TermMapping(source_term="电机", target_term="电动机", priority=5),
    TermMapping(source_term="泵", target_term="水泵", priority=5),
    TermMapping(source_term="风机", target_term="通风机", priority=5),
    TermMapping(source_term="空压机", target_term="空气压缩机", priority=10),
    TermMapping(source_term="压缩机", target_term="压缩机", priority=0),  # 保底
    # ---- 故障现象同义词 ----
    TermMapping(source_term="异响", target_term="异常噪音", priority=8),
    TermMapping(source_term="漏油", target_term="泄漏润滑油", priority=8),
    TermMapping(source_term="温升", target_term="温度升高", priority=8),
    TermMapping(source_term="过热", target_term="温度过高", priority=8),
    TermMapping(source_term="振动大", target_term="异常振动", priority=8),
    TermMapping(source_term="异音", target_term="异常噪音", priority=8),
    TermMapping(source_term="不转", target_term="无法启动", priority=8),
    # ---- 参数类 ----
    TermMapping(source_term="轴温", target_term="轴承温度", priority=10),
    TermMapping(source_term="油温", target_term="润滑油温度", priority=10),
    TermMapping(source_term="水压", target_term="冷却水压力", priority=10),
    # ---- 口语 → 书面 ----
    TermMapping(source_term="怎么回事", target_term="原因分析", priority=8),
    TermMapping(source_term="怎么处理", target_term="处理方法", priority=8),
    TermMapping(source_term="怎么办", target_term="处理方法", priority=8),
    TermMapping(source_term="啥原因", target_term="原因分析", priority=8),
    TermMapping(source_term="多少算正常", target_term="正常工作范围", priority=8),
    TermMapping(source_term="多少算超标", target_term="报警阈值", priority=8),
]


class QueryTermMappingService:
    """术语归一化服务 — 规则化同义词/缩写映射"""

    def __init__(self, mappings: Optional[List[TermMapping]] = None):
        self._mappings = self._compile(mappings or DEFAULT_MAPPINGS)

    def normalize(self, text: str) -> str:
        """
        对文本做术语归一化。
        - 按 priority 从高到低依次替换
        - 长词优先匹配（避免短词误替换长词中的子串）
        """
        if not text or not text.strip():
            return text

        result = text
        for pattern, replacement in self._mappings:
            result = pattern.sub(replacement, result)

        return result

    def _compile(
        self, mappings: List[TermMapping]
    ) -> List[tuple[re.Pattern, str]]:
        """编译映射规则，按优先级 + 源词长度降序排列"""
        sorted_mappings = sorted(
            (m for m in mappings if m.enabled),
            key=lambda m: (m.priority, len(m.source_term)),
            reverse=True,
        )
        compiled = []
        for m in sorted_mappings:
            # 全词匹配，避免 "电机" 匹配到 "电动机" 中的 "电机"
            pattern = re.compile(re.escape(m.source_term))
            compiled.append((pattern, m.target_term))
        return compiled


# 单例
_service: Optional[QueryTermMappingService] = None


def get_term_mapping_service() -> QueryTermMappingService:
    """获取全局归一化服务单例"""
    global _service
    if _service is None:
        _service = QueryTermMappingService()
    return _service
