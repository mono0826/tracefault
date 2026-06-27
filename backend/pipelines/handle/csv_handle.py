import os
import csv

from .base_handle import BaseFileHandler
from ..models import Document, FileType


class CsvFileHandler(BaseFileHandler):
    def process(self, file: str) -> Document:
        """
        读取CSV文件并转换为文本

        注意：此方法将CSV转为纯文本，暂不支持结构化数据处理
        """
        try:
            text = []
            with open(file, 'r', encoding='utf-8', errors='replace') as f:
                csv_reader = csv.reader(f)
                for row in csv_reader:
                    text.append(','.join(row))
            content = '\n'.join(text)

            return Document(
                file_name=file,
                file_type=FileType.CSV,
                file_path=os.path.basename(file),
                file_size=os.path.getsize(file),
                file_content=content,
                status="success"
            )
        except Exception as e:
            print(f"读取CSV文件 {os.path.basename(file)} 失败: {str(e)}")
            # 尝试其他编码
            try:
                with open(file, 'rb') as f:
                    try:
                        import chardet
                        raw_data = f.read(10240)
                        result = chardet.detect(raw_data)
                        encoding = result['encoding'] if result['encoding'] else 'gbk'
                    except:
                        encoding = 'gbk'

                text = []
                with open(file, 'r', encoding=encoding, errors='replace') as f:
                    csv_reader = csv.reader(f)
                    for row in csv_reader:
                        text.append(','.join(row))
                content = '\n'.join(text)

                return Document(
                    file_name=file,
                    file_type=FileType.CSV,
                    file_path=os.path.basename(file),
                    file_size=os.path.getsize(file),
                    file_content=content,
                    status="success"
                )
            except Exception as e2:
                print(f"尝试使用其他编码读取CSV失败: {str(e2)}")
                return Document(
                    file_name=file,
                    file_type=FileType.CSV,
                    file_path=os.path.basename(file),
                    file_size=os.path.getsize(file),
                    file_content=f"[无法读取CSV文件内容: {str(e)}]",
                    status="failed"
                )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test"
    test_file = data_dir / "test.csv"

    handler = CsvFileHandler()

    if test_file.exists():
        result = handler.process(str(test_file))
        print(f"\n=== CsvFileHandler 测试 ===")
        print(f"文件名: {result.file_name}")
        print(f"文件类型: {result.file_type}")
        print(f"文件路径: {result.file_path}")
        print(f"文件大小: {result.file_size} 字节")
        print(f"状态: {result.status}")
        print(f"内容预览:\n{result.file_content[:500]}...")
    else:
        print(f"\n测试文件不存在: {test_file}，跳过 CsvFileHandler 测试")
        print("提示: 可以将 .csv 文件放入 data/test/ 目录后测试")
