import hashlib
from typing import List, Optional
from enum import Enum
from dataclasses import dataclass


class FileType(Enum):
    TXT = "txt"
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    MD = "md"
    CSV = "csv"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"


@dataclass
class Document:
    file_name: str
    file_type: str
    file_path: str
    file_size: int
    file_content: str
    status: str
    file_hash: str = ""

    def __post_init__(self):
        """自动计算文件的 SHA256 哈希（基于原始二进制）"""
        if not self.file_hash and self.file_path:
            try:
                with open(self.file_path, "rb") as f:
                    self.file_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass

    def __str__(self):
        preview = (self.file_content[:80] + "...") if len(self.file_content) > 80 else self.file_content
        return (
            f"Document(\n"
            f"  file_name : {self.file_name}\n"
            f"  file_type : {self.file_type}\n"
            f"  file_size : {self.file_size} bytes\n"
            f"  status    : {self.status}\n"
            f"  file_hash : {self.file_hash[:16]}...\n"
            f"  file_content   : {preview}\n"
            f")"
        )

    def __repr__(self):
        return self.__str__()


@dataclass
class Chunk:
    """文本分块，记录来源文档和块内序号"""
    file_path: str         # chunk 所在的文件路径(Document.file_path)
    chunk_id: str = ""     # 唯一标识，空时由 content SHA1 自动生成
    doc_id: str = ""       # 来源文档标识（Document.file_hash）
    content: str = ""      # 分块文本内容

    def __post_init__(self):
        """自动计算文件内容的 SHA1 哈希"""
        if not self.chunk_id and self.content:
            self.chunk_id = hashlib.sha1(self.content.encode("utf-8")).hexdigest()

    def __str__(self):
        # preview = (self.content[:80] + "...") if len(self.content) > 80 else self.content
        return (
            f"Chunk(\n"
            f"  file_path : {self.file_path}\n"
            f"  chunk_id  : {self.chunk_id}\n"
            f"  doc_id    : {self.doc_id}\n"
            f"  content   : {self.content}\n"
            f")"
        )

    def __repr__(self):
        return self.__str__()
