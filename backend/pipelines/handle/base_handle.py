from abc import ABC, abstractmethod

from ..models import Document

class BaseFileHandler(ABC):
    @abstractmethod
    def process(self, file: str) -> Document:
        """处理单个文件，返回一个 Document 对象"""
        pass
