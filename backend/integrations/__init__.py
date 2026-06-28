"""
外部集成和辅助工具 — 知识图谱构建与增量更新

对外使用方式：
    from backend.integrations import KnowledgeGraphProcessor
    from backend.integrations import KnowledgeGraphBuilder
    from backend.integrations import IncrementalUpdateManager
"""

from backend.integrations.main import KnowledgeGraphProcessor
from backend.integrations.build.build_graph import KnowledgeGraphBuilder
from backend.integrations.build.build_index_and_community import IndexCommunityBuilder
from backend.integrations.build.build_chunk_index import ChunkIndexBuilder
from backend.integrations.build.incremental_update import IncrementalUpdateManager

__all__ = [
    "KnowledgeGraphProcessor",
    "KnowledgeGraphBuilder",
    "IndexCommunityBuilder",
    "ChunkIndexBuilder",
    "IncrementalUpdateManager",
]
