import os
from typing import Dict, List, Optional, Union

from .handle import (
    Document,
    BaseFileHandler,
    CsvFileHandler,
    DocFileHandler,
    DocxFileHandler,
    JsonFileHandler,
    MarkdownFileHandler,
    PdfFileHandler,
    TxtFileHandler,
    YamlFileHandler,
)


class FileReader:
    """
    文件读取器，支持多种文件格式：
    - TXT (文本文件)
    - PDF (PDF文档)
    - MD (Markdown文件)
    - DOCX (Word文档)
    - DOC (旧版Word文档)
    - CSV (CSV文件)
    - JSON (JSON文件)
    - YAML/YML (YAML文件)
    """

    def __init__(self, directory_path: Optional[str] = None):
        """
        初始化文件读取器

        Args:
            directory_path: 文件目录路径。为 None 时只能使用 file_paths 参数读取指定文件。
        """
        self.directory_path = directory_path
        self._handlers: Dict[str, BaseFileHandler] = {
            '.txt': TxtFileHandler(),
            '.pdf': PdfFileHandler(),
            '.md': MarkdownFileHandler(),
            '.docx': DocxFileHandler(),
            '.doc': DocFileHandler(),
            '.csv': CsvFileHandler(),
            '.json': JsonFileHandler(),
            '.yaml': YamlFileHandler(),
            '.yml': YamlFileHandler(),
        }

    # pubilc 接口
    def read_files(
        self,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ) -> List[Document]:
        """
        读取文件

        Args:
            file_extensions: 文件扩展名列表，如 ['.txt', '.pdf']，如不指定则读取所有支持的格式
            recursive: 是否递归读取子目录，默认为True（仅扫描目录时有效）
            file_paths: 指定要处理的文件路径。
                        为 None 时扫描 directory_path 目录；
                        为 str 时处理单个文件；
                        为 List[str] 时处理多个文件。
            directory_path: 要扫描的目录路径，动态覆盖 __init__ 时传入的路径。

        Returns:
            List[Document]: Document 对象列表
        """
        if file_extensions is None:
            file_extensions = list(self._handlers.keys())

        # 指定文件路径 → 直接处理
        if file_paths is not None:
            paths = [file_paths] if isinstance(file_paths, str) else file_paths
            return [self._process_single_file(p) for p in paths]

        # 确定扫描目录：优先用调用时传入的，其次用实例化时传入的
        scan_dir = directory_path or self.directory_path
        if scan_dir is None:
            raise ValueError("请传入 directory_path 或 file_paths")

        results: List[Document] = []
        try:
            if recursive:
                results = self._read_files_recursive(scan_dir, file_extensions)
            else:
                all_filenames = os.listdir(scan_dir)
                results = self._process_files_in_dir(scan_dir, all_filenames, file_extensions)
        except Exception as e:
            print(f"列出目录 {scan_dir} 中的文件时出错: {str(e)}")

        return results

    def list_all_files(self, recursive: bool = True) -> List[str]:
        """
        列出目录中的所有文件

        Args:
            recursive: 是否递归列出子目录中的文件，默认为True

        Returns:
            List[str]: 文件路径列表（相对于根目录）
        """
        files = []

        try:
            if recursive:
                for root, _, filenames in os.walk(self.directory_path):
                    for filename in filenames:
                        rel_path = os.path.relpath(os.path.join(root, filename), self.directory_path)
                        files.append(rel_path)
            else:
                files = os.listdir(self.directory_path)
        except Exception as e:
            print(f"列出目录文件时出错: {str(e)}")

        return files

    # private 接口
    def _process_single_file(self, file_path: str) -> Document:
        """处理单个文件路径，返回 Document"""
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in self._handlers:
            print(f"处理文件: {os.path.basename(file_path)} (类型: {file_ext})")
            return self._handlers[file_ext].process(file_path)
        return Document(
            file_name=file_path,
            file_type="",
            file_path=os.path.basename(file_path),
            file_size=os.path.getsize(file_path),
            file_content=f"[不支持的格式: {file_ext}]",
            status="failed",
        )

    def _read_files_recursive(self, root_dir: str, file_extensions: List[str]) -> List[Document]:
        """
        递归读取目录及其子目录中的文件

        Args:
            root_dir: 当前处理的目录路径
            file_extensions: 要处理的文件扩展名列表

        Returns:
            List[Document]: Document 对象列表
        """
        results: List[Document] = []

        try:
            for item in os.listdir(root_dir):
                item_path = os.path.join(root_dir, item)

                if os.path.isdir(item_path):
                    print(f"递归进入子目录: {item_path}")
                    sub_results = self._read_files_recursive(item_path, file_extensions)
                    results.extend(sub_results)

                elif os.path.isfile(item_path):
                    file_ext = os.path.splitext(item)[1].lower()

                    if file_ext in file_extensions:
                        rel_path = os.path.relpath(item_path, self.directory_path)
                        print(f"处理文件: {rel_path} (类型: {file_ext})")

                        if file_ext in self._handlers:
                            doc: Document = self._handlers[file_ext].process(item_path)
                            results.append(doc)
                            print(f"成功读取文件: {rel_path}, 内容长度: {len(doc.file_content)}")
        except Exception as e:
            print(f"列出目录 {root_dir} 中的文件时出错: {str(e)}")

        return results

    def _process_files_in_dir(self, directory: str, filenames: List[str],
                               file_extensions: List[str]) -> List[Document]:
        """
        处理指定目录中的文件（不递归）

        Args:
            directory: 目录路径
            filenames: 文件名列表
            file_extensions: 要处理的文件扩展名列表

        Returns:
            List[Document]: Document 对象列表
        """
        results: List[Document] = []

        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()

            if file_ext in file_extensions:
                file_path = os.path.join(directory, filename)
                print(f"处理文件: {filename} (类型: {file_ext})")

                if file_ext in self._handlers:
                    doc: Document = self._handlers[file_ext].process(file_path)
                    results.append(doc)
                    print(f"成功读取文件: {filename}, 内容长度: {len(doc.file_content)}")

        return results



# 测试代码
if __name__ == '__main__':
    import sys
    from pathlib import Path

    # 确保项目根目录在 sys.path 中，以便导入 backend 包
    _project_root = str(Path(__file__).resolve().parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    FILES_DIR = "F:/AllProjects/Agent/equipment-fault-qa/data/test"
    print(f"FILES_DIR: {FILES_DIR}")
    reader = FileReader(FILES_DIR)

    # 列出目录中的所有文件
    all_filenames = reader.list_all_files()
    print(f"目录中共有 {len(all_filenames)} 个文件:")
    for filename in all_filenames:
        print(f"  {filename}")

    # 测试读取所有支持的文件
    all_docs = reader.read_files()
    print(f"成功读取 {len(all_docs)} 个文件")

    # 显示每种类型文件的数量
    file_types = {}
    for doc in all_docs:
        ext = os.path.splitext(doc.file_name)[1].lower()
        file_types[ext] = file_types.get(ext, 0) + 1

    print("Files by type:")
    for ext, count in file_types.items():
        print(f"  {ext}: {count}")

    # 显示文件详情
    print("\n文件详情:")
    for doc in all_docs:
        print(f"  - {doc.file_name}")
        print(f"    类型: {doc.file_type}")
        print(f"    大小: {doc.file_size} 字节")
        print(f"    状态: {doc.status}")
        print(f"    内容长度: {len(doc.file_content)} 字符")
