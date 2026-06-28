from typing import List, Optional, Union

from rich.console import Console
from rich.panel import Panel
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
                self._run_incremental(file_paths, directory_path)
            else:
                self._run_full(file_paths, directory_path)
        except Exception as e:
            error_text = Text(f"处理过程中出现错误: {str(e)}", style="bold red")
            self.console.print(Panel(error_text, border_style="red"))
            raise

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
        graph_builder = KnowledgeGraphBuilder()
        graph_builder.process(file_paths=file_paths, directory_path=directory_path)

        self.console.print("\n[bold cyan]步骤 2: 构建实体索引和社区[/bold cyan]")
        IndexCommunityBuilder().process()

        self.console.print("\n[bold cyan]步骤 3: 构建Chunk索引[/bold cyan]")
        ChunkIndexBuilder().process()

        success_text = Text("完整构建完成", style="bold green")
        self.console.print(Panel(success_text, border_style="green"))

    def _run_incremental(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ):
        """增量更新：只处理变更的文件"""
        start_text = Text("增量更新模式", style="bold yellow")
        self.console.print(Panel(start_text, border_style="yellow"))

        updater = IncrementalUpdateManager()
        updater.process(
            file_paths=file_paths,
            directory_path=directory_path
        )

        success_text = Text("增量更新完成", style="bold green")
        self.console.print(Panel(success_text, border_style="green"))
