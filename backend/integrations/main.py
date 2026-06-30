from typing import List, Optional, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.graph.core import connection_manager
from backend.integrations.build.build_graph import KnowledgeGraphBuilder
from backend.integrations.build.build_index_and_community import IndexCommunityBuilder
from backend.integrations.build.build_chunk_index import ChunkIndexBuilder
from backend.integrations.build.incremental_update import IncrementalUpdateManager
from backend.config.settings import FILES_DIR


class KnowledgeGraphProcessor:
    """
    知识图谱处理器，整合了图谱构建和索引处理的完整流程。
    支持完整构建和增量更新两种模式。
    """

    def __init__(self):
        """初始化知识图谱处理器"""
        self.console = Console()
        self.graph_builder = KnowledgeGraphBuilder()
        self.index_community_builder = IndexCommunityBuilder()
        self.chunk_index_builder = ChunkIndexBuilder()
        self.incremental_updater = IncrementalUpdateManager()

    def process_all(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
        incremental: bool = False,
    ):
        """
        执行完整的处理流程

        Args:
            file_paths: 指定要处理的文件路径，为 None 时扫描目录
            directory_path: 要扫描的目录路径
            incremental: 是否使用增量更新模式，为 True 时只处理新增和修改的文件
        """
        try:
            if incremental:
                # 检查是否已有图谱数据，没有则自动切到全量构建
                try:
                    from backend.config.neo4jdb import get_db_manager
                    r = get_db_manager().graph.query("MATCH (e:__Entity__) RETURN count(e) AS c")
                    has_graph = r and r[0].get("c", 0) > 0
                except Exception:
                    has_graph = False

                if not has_graph:
                    self.console.print("[yellow]未检测到图谱数据，增量更新切换到全量构建模式[/yellow]")
                    self._run_full(file_paths, directory_path)
                else:
                    self._run_incremental(file_paths, directory_path)
            else:
                self._run_full(file_paths, directory_path)
        except Exception as e:
            error_text = Text(f"处理过程中出现错误: {str(e)}", style="bold red")
            self.console.print(Panel(error_text, border_style="red"))
            raise

    def has_graph(self) -> bool:
        """检查是否已构建知识图谱"""
        try:
            from backend.config.neo4jdb import get_db_manager
            r = get_db_manager().graph.query("MATCH (e:__Entity__) RETURN count(e) AS c LIMIT 1")
            return r and r[0].get("c", 0) > 0
        except Exception:
            return False

    def update_graph(self):
        self.incremental_updater.update()

    def get_stats(self) -> dict:
        """获取知识图谱统计（实体、关系、Chunk、社区）"""
        try:
            from backend.config.neo4jdb import get_db_manager
            db = get_db_manager()
            r = db.graph.query("""
                MATCH (e:__Entity__) WITH count(e) AS entities
                MATCH ()-[r]->() WITH entities, count(r) AS relations
                MATCH (c:__Chunk__) WITH entities, relations, count(c) AS chunks
                MATCH (m:__Community__) WITH entities, relations, chunks, count(m) AS communities
                RETURN entities, relations, chunks, communities
            """)
            row = r[0] if r else {}
            return {
                "entities": row.get("entities", 0),
                "relations": row.get("relations", 0),
                "chunks": row.get("chunks", 0),
                "communities": row.get("communities", 0),
            }
        except Exception:
            return {"entities": 0, "relations": 0, "chunks": 0, "communities": 0}

    def _run_full(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ):
        """完整构建：清除旧数据后重新构建"""
        start_text = Text("完整构建模式", style="bold cyan")
        self.console.print(Panel(start_text, border_style="cyan"))

        self.console.print("\n[bold yellow]步骤 0: 清除所有旧索引[/bold yellow]")
        connection_manager.drop_all_indexes()

        self.console.print("\n[bold cyan]步骤 1: 构建基础图谱[/bold cyan]")
        result = self.graph_builder.process(file_paths=file_paths, directory_path=directory_path)

        if not result:
            self.console.print("[yellow]步骤 1 未提取到实体，跳过后续步骤[/yellow]")
            return

        self.console.print("\n[bold cyan]步骤 2: 构建实体索引和社区[/bold cyan]")
        self.index_community_builder.process()

        self.console.print("\n[bold cyan]步骤 3: 构建Chunk索引[/bold cyan]")
        self.chunk_index_builder.process()

        success_text = Text("完整构建完成", style="bold green")
        self.console.print(Panel(success_text, border_style="green"))

        stats = self.get_stats()
        tbl = Table(title="图谱统计")
        tbl.add_column("指标", style="cyan")
        tbl.add_column("数量", justify="right")
        tbl.add_row("实体", str(stats["entities"]))
        tbl.add_row("关系", str(stats["relations"]))
        tbl.add_row("Chunk", str(stats["chunks"]))
        tbl.add_row("社区", str(stats["communities"]))
        self.console.print(tbl)

    def _run_incremental(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ):
        """增量更新：只处理变更的文件"""
        start_text = Text("增量更新模式", style="bold yellow")
        self.console.print(Panel(start_text, border_style="yellow"))

        self.incremental_updater.process(
            file_paths=file_paths,
            directory_path=directory_path
        )

        stats = self.get_stats()
        tbl = Table(title="图谱统计")
        tbl.add_column("指标", style="cyan")
        tbl.add_column("数量", justify="right")
        tbl.add_row("实体", str(stats["entities"]))
        tbl.add_row("关系", str(stats["relations"]))
        tbl.add_row("Chunk", str(stats["chunks"]))
        tbl.add_row("社区", str(stats["communities"]))
        self.console.print(tbl)

        success_text = Text("增量更新完成", style="bold green")
        self.console.print(Panel(success_text, border_style="green"))
