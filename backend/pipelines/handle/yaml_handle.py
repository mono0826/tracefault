import os
import yaml
from yaml import CLoader as Loader

from .base_handle import BaseFileHandler
from ..models import Document, FileType


class YamlFileHandler(BaseFileHandler):
    def process(self, file: str) -> Document:
        """读取YAML文件并返回文本格式"""
        try:
            with open(file, 'r', encoding='utf-8', errors='replace') as f:
                data = yaml.load(f, Loader=Loader)
            content = yaml.dump(data, allow_unicode=True, default_flow_style=False)

            return Document(
                file_name=os.path.basename(file),
                file_type=FileType.YAML,
                file_path=file,
                file_size=os.path.getsize(file),
                file_content=content,
                status="success"
            )
        except Exception as e:
            print(f"读取YAML文件 {os.path.basename(file)} 失败: {str(e)}")
            return Document(
                file_name=os.path.basename(file),
                file_type=FileType.YAML,
                file_path=file,
                file_size=os.path.getsize(file),
                file_content=f"[无法读取YAML文件内容: {str(e)}]",
                status="failed"
            )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test"
    test_file = data_dir / "test.yaml"

    handler = YamlFileHandler()

    if test_file.exists():
        result = handler.process(str(test_file))
        print(f"\n=== YamlFileHandler 测试 ===")
        print(f"文件名: {result.file_name}")
        print(f"文件类型: {result.file_type}")
        print(f"文件路径: {result.file_path}")
        print(f"文件大小: {result.file_size} 字节")
        print(f"状态: {result.status}")
        print(f"内容预览:\n{result.file_content[:500]}...")
    else:
        print(f"\n测试文件不存在: {test_file}，跳过 YamlFileHandler 测试")
        print("提示: 可以将 .yaml 文件放入 data/test/ 目录后测试")
