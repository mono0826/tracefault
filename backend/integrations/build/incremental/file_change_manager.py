import os
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from backend.config.settings import FILE_REGISTRY_PATH, FILES_DIR


class FileChangeManager:
    """
    文件变更管理器，负责追踪文件的变更状态。

    主要功能：
    1. 扫描文件目录，计算文件哈希值
    2. 与历史记录比较，识别变更的文件
    3. 更新文件注册表
    """

    def __init__(self, files_dir: Optional[str] = FILES_DIR, registry_path: str = None):
        """
        初始化文件变更管理器

        Args:
            files_dir: 要监控的文件目录（可选，也可通过 detect_changes 动态传入）
            registry_path: 文件注册表保存路径，默认使用配置中的路径
        """
        if registry_path is None:
            registry_path = str(FILE_REGISTRY_PATH)

        self.files_dir = Path(files_dir) if files_dir else None
        self.registry_path = Path(registry_path)
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """
        加载文件注册表

        Returns:
            Dict: 文件注册表，键为文件路径，值为文件元数据
        """
        if not self.registry_path.exists():
            return {}

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"无法加载文件注册表，将创建新的注册表")
            return {}

    def _save_registry(self):
        """保存文件注册表到磁盘"""
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, ensure_ascii=False, indent=2)

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        计算文件的SHA256哈希值

        Args:
            file_path: 文件路径

        Returns:
            str: 文件哈希值
        """
        try:
            return hashlib.sha256(file_path.read_bytes()).hexdigest()
        except Exception as e:
            print(f"计算文件哈希值失败: {file_path}, 错误: {e}")
            return ""

    def _scan_current_files(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        扫描指定目录或文件列表，返回文件状态

        Args:
            file_paths: 单个文件路径或文件路径列表
            directory_path: 目录路径

        Returns:
            Dict: 当前文件状态，键为文件名，值为文件元数据
        """
        scan_dir = Path(directory_path) if directory_path else self.files_dir
        current_files = {}

        if scan_dir and scan_dir.exists():
            for root, _, files in os.walk(scan_dir):
                for filename in files:
                    fp = Path(root) / filename
                    fhash = self._compute_file_hash(fp)
                    if not fhash:
                        continue
                    current_files[filename] = {
                        "hash": fhash,
                        "size": fp.stat().st_size,
                        "last_modified": fp.stat().st_mtime,
                        "last_scanned": time.time(),
                    }

        if file_paths:
            if isinstance(file_paths, str):
                file_paths = [file_paths]
            for fp_str in file_paths:
                fp = Path(fp_str)
                if not fp.exists() or not fp.is_file():
                    continue
                fhash = self._compute_file_hash(fp)
                if fhash:
                    current_files[fp.name] = {
                        "hash": fhash,
                        "size": fp.stat().st_size,
                        "last_modified": fp.stat().st_mtime,
                        "last_scanned": time.time(),
                    }

        return current_files

    def detect_changes(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        检测文件变更（只读，不更新注册表）

        Args:
            file_paths: 单个文件路径或文件路径列表
            directory_path: 目录路径

        Returns:
            Dict: 包含三种变更类型的文件列表：added, modified, deleted
        """
        current_files = self._scan_current_files(file_paths, directory_path)
        added_files, modified_files, deleted_files = [], [], []

        for filename, file_info in current_files.items():
            if filename not in self.registry:
                added_files.append(filename)
            elif file_info["hash"] != self.registry[filename]["hash"]:
                modified_files.append(filename)

        for filename in self.registry:
            if filename not in current_files:
                deleted_files.append(filename)

        return {"added": added_files, "modified": modified_files, "deleted": deleted_files}

    def process(
        self,
        file_paths: Optional[Union[str, List[str]]] = None,
        directory_path: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        检测文件变更并更新注册表（detect + update）

        Args:
            file_paths: 单个文件路径或文件路径列表
            directory_path: 目录路径

        Returns:
            Dict: 包含三种变更类型的文件列表：added, modified, deleted
        """
        result = self.detect_changes(file_paths, directory_path)
        self.registry = self._scan_current_files(file_paths, directory_path)
        self._save_registry()

        print(f"[FileChangeManager] 新增 {len(result['added'])}, 修改 {len(result['modified'])}, 删除 {len(result['deleted'])}")
        return result

    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件元数据

        Args:
            file_path: 文件名

        Returns:
            Dict: 文件元数据
        """
        return self.registry.get(file_path, {})

    def update_registry(self):
        """更新文件注册表，记录当前所有文件的状态"""
        self.registry = self._scan_current_files()
        self._save_registry()
        print(f"文件注册表已更新，共记录 {len(self.registry)} 个文件")

    def update_file_status(self, file_path: str, status: Dict[str, Any]):
        """
        更新单个文件的状态

        Args:
            file_path: 文件名
            status: 文件状态
        """
        if file_path in self.registry:
            self.registry[file_path].update(status)
            self._save_registry()

    def register_file_processing(self, file_path: str, processing_info: Dict[str, Any]):
        """
        记录文件处理信息

        Args:
            file_path: 文件名
            processing_info: 处理信息（如处理时间、节点数等）
        """
        if file_path in self.registry:
            if "processing_history" not in self.registry[file_path]:
                self.registry[file_path]["processing_history"] = []
            processing_record = {"timestamp": datetime.now().isoformat(), **processing_info}
            self.registry[file_path]["processing_history"].append(processing_record)
            self.registry[file_path]["last_processed"] = processing_record["timestamp"]
            self._save_registry()
