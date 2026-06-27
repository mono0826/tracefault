import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Union

# 确保项目根目录在 sys.path 中，支持直接脚本执行
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from .file_reader import FileReader
from .text_chunker import ChineseTextChunker
from .models import Document, Chunk
from backend.config.settings import FILES_DIR, CHUNK_SIZE, OVERLAP


class DocumentProcessor:
    """
    文档处理器，用于整合文件读取、文本分块和向量操作等功能
    """

    def __init__(self, directory_path: Optional[str] = None, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP):
        """
        初始化文档处理器

        Args:
            directory_path: 文件目录路径，为 None 时需在 process_directory 中传入
            chunk_size: 分块大小
            overlap: 分块重叠大小
        """
        self.directory_path = directory_path
        self.file_reader = FileReader(directory_path)
        self.chunker = ChineseTextChunker(chunk_size, overlap)

    def process(
        self,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ) -> List[Chunk]:
        """
        读取文件并分块，返回 Chunk 列表

        Args:
            file_extensions: 文件扩展名列表，如不指定则读取所有支持的格式
            recursive: 是否递归读取子目录，默认为 True
            file_paths: 指定要处理的文件路径，为 None 时扫描目录
            directory_path: 要扫描的目录路径，动态覆盖 __init__ 时传入的路径

        Returns:
            List[Chunk]: 全部文档的分块列表
        """
        docs = self.file_reader.read_files(
            file_extensions=file_extensions,
            recursive=recursive,
            file_paths=file_paths,
            directory_path=directory_path,
        )
        print(f"DocumentProcessor找到的文件数量: {len(docs)}")

        all_chunks: List[Chunk] = []
        for doc in docs:
            if doc.status == "failed":
                print(f"  {doc.file_name}: 状态为 failed，需要重新上传。")
                continue
            doc_chunks = self._process_single_document(doc)
            all_chunks.extend(doc_chunks)

        print(f"分块完成，总共 {len(all_chunks)} 个 Chunk")
        return all_chunks

    def _process_single_document(self, doc: Document) -> List[Chunk]:
        """对单个 Document 进行分块，返回 Chunk 列表"""
        try:
            chunks = self.chunker.chunk_document(doc)
        except Exception as e:
            print(f"分块错误 ({doc.file_name}): {str(e)}")
            return []
        print(f"  {doc.file_name}: {len(chunks)} 个 Chunk")
        return chunks

    def get_file_stats(
        self,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        获取目录中文件的统计信息

        Args:
            file_extensions: 指定要统计的文件扩展名，如不指定则处理所有支持的类型
            recursive: 是否递归统计子目录，默认为True

        Returns:
            Dict: 文件统计信息
        """
        docs = self.file_reader.read_files(file_extensions, recursive=recursive)

        extension_counts: Dict[str, int] = {}
        total_content_length = 0
        directories: set = set()

        for doc in docs:
            filepath = doc.file_name
            ext = os.path.splitext(filepath)[1].lower()
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

            dirpath = os.path.dirname(filepath)
            if dirpath:
                directories.add(dirpath)

            if doc.file_content is not None:
                total_content_length += len(doc.file_content)
            else:
                print(f"警告: 文件 {filepath} 的内容为None")

        return {
            "total_files": len(docs),
            "extension_counts": extension_counts,
            "total_content_length": total_content_length,
            "average_file_length": total_content_length / len(docs) if docs else 0,
            "directories": list(directories),
            "directory_count": len(directories),
        }

    @staticmethod
    def get_extension_type(extension: str) -> str:
        """
        获取文件扩展名对应的文档类型

        Args:
            extension: 文件扩展名（包括'.'，如'.pdf'）

        Returns:
            str: 文档类型描述
        """
        extension_types = {
            ".txt": "文本文件",
            ".pdf": "PDF文档",
            ".md": "Markdown文档",
            ".doc": "Word文档",
            ".docx": "Word文档",
            ".csv": "CSV数据文件",
            ".json": "JSON数据文件",
            ".yaml": "YAML配置文件",
            ".yml": "YAML配置文件",
        }
        return extension_types.get(extension.lower(), "未知类型")


if __name__ == "__main__":
    processor = DocumentProcessor(FILES_DIR)

    # 读取 → 分块 → 得到 Chunk 列表
    chunks = processor.process_directory(recursive=True)
    print(f"\n共生成 {len(chunks)} 个 Chunk")

    # 按来源文档统计
    doc_stats: Dict[str, int] = {}
    for c in chunks:
        doc_stats[c.doc_id] = doc_stats.get(c.doc_id, 0) + 1

    print("\n各文档分块数量:")
    for doc_id, count in doc_stats.items():
        print(f"  {doc_id}: {count} 块")

    # 显示前 3 个 Chunk 预览
    print("\n前 3 个 Chunk 预览:")
    for c in chunks[:2]:
        print(f"  [{c.chunk_id}] {c.content}...")
        print("="*60)
