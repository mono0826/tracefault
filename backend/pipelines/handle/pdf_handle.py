import os
import codecs
import PyPDF2

from .base_handle import BaseFileHandler
from ..models import Document, FileType


class PdfFileHandler(BaseFileHandler):
    def process(self, file: str) -> Document:
        """读取PDF文件"""
        try:
            text = ""
            with open(file, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_num in range(len(pdf_reader.pages)):
                    try:
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text() or ""
                        text += page_text + "\n\n"
                    except Exception as e:
                        print(f"读取PDF文件 {os.path.basename(file)} 的第 {page_num+1} 页失败: {str(e)}")
                        text += f"[第 {page_num+1} 页无法读取]\n\n"

            return Document(
                file_name=file,
                file_type=FileType.PDF,
                file_path=os.path.basename(file),
                file_size=os.path.getsize(file),
                file_content=text,
                status="success"
            )

        except Exception as e:
            print(f"读取PDF文件 {os.path.basename(file)} 失败: {str(e)}")
            return Document(
                file_name=file,
                file_type=FileType.PDF,
                file_path=os.path.basename(file),
                file_size=os.path.getsize(file),
                file_content=f"[无法读取文件内容: {str(e)}]",
                status="failed"
            )


if __name__ == "__main__":
    import sys
    from pathlib import Path

    project_root = str(Path(__file__).resolve().parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test"
    test_file = data_dir / "test.pdf"

    handler = PdfFileHandler()

    if test_file.exists():
        result = handler.process(str(test_file))
        print(f"\n=== PdfFileHandler 测试 ===")
        print(f"文件名: {result.file_name}")
        print(f"文件类型: {result.file_type}")
        print(f"文件路径: {result.file_path}")
        print(f"文件大小: {result.file_size} 字节")
        print(f"状态: {result.status}")
        print(f"内容预览:\n{result.file_content[:500]}...")
    else:
        print(f"\n测试文件不存在: {test_file}")