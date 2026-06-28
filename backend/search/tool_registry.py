"""
搜索工具注册表

集中列出LangChain可调用的搜索类，便于多Agent层统一引用。
"""

from typing import Any, Dict, Type

from backend.search.tool.base import BaseSearchTool
from backend.search.tool.local_search_tool import LocalSearchTool
from backend.search.tool.global_search_tool import GlobalSearchTool
from backend.search.tool.hybrid_tool import HybridSearchTool
from backend.search.tool.naive_search_tool import NaiveSearchTool
from backend.search.tool.deep_research_tool import DeepResearchTool
from backend.search.tool.deeper_research_tool import DeeperResearchTool
from backend.search.tool.chain_exploration_tool import ChainOfExplorationTool
from backend.search.tool.hypothesis_tool import HypothesisGeneratorTool
from backend.search.tool.validation_tool import AnswerValidationTool

TOOL_REGISTRY: Dict[str, Type[BaseSearchTool]] = {
    "local_search": LocalSearchTool,
    "global_search": GlobalSearchTool,
    "hybrid_search": HybridSearchTool,
    "naive_search": NaiveSearchTool,
    "deep_research": DeepResearchTool,
    "deeper_research": DeeperResearchTool,
}

# 额外暴露的专用工具（不继承BaseSearchTool）
EXTRA_TOOL_FACTORIES: Dict[str, Any] = {
    "chain_exploration": ChainOfExplorationTool,
    "hypothesis_generator": HypothesisGeneratorTool,
    "answer_validator": AnswerValidationTool,
}


def get_tool_class(tool_name: str) -> Type[BaseSearchTool]:
    """根据名称获取工具类，若不存在则抛出KeyError"""
    return TOOL_REGISTRY[tool_name]


def available_tools() -> Dict[str, Type[BaseSearchTool]]:
    """返回注册表的浅拷贝"""
    return dict(TOOL_REGISTRY)


def available_extra_tools() -> Dict[str, Any]:
    """返回额外工具工厂的浅拷贝"""
    return dict(EXTRA_TOOL_FACTORIES)


def create_extra_tool(tool_name: str) -> Any:
    """根据名称创建额外工具实例。"""
    factory = EXTRA_TOOL_FACTORIES[tool_name]
    return factory()


__all__ = [
    "TOOL_REGISTRY",
    "EXTRA_TOOL_FACTORIES",
    "get_tool_class",
    "available_tools",
    "available_extra_tools",
    "create_extra_tool",
]
