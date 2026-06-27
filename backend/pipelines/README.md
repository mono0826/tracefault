# pipelines 模块 — 文档处理流水线

提供完整的文档处理链：**文件读取 → 文本分块**，支持多种格式的文档解析与中文文本智能分割。

---

## 目录结构

```
pipelines/
├── __init__.py              # 模块入口（空）
├── README.md                # 本文件
├── models.py                # 数据类：Document / Chunk / FileType
├── file_reader.py           # 文件读取器 - 遍历目录、按格式解析文件
├── text_chunker.py          # 中文文本分块器 - HanLP分词、滑动窗口分块
├── document_processor.py    # 文档处理器 - 整合读取+分块的高层接口
└── handle/                  # 格式处理器（每种文件格式一个）
    ├── __init__.py           # 导出所有 Handler
    ├── base_handle.py        # 基类 BaseFileHandler
    ├── txt_handle.py         # TXT 文件处理器
    ├── pdf_handle.py         # PDF 文件处理器 (PyPDF2)
    ├── md_handle.py          # Markdown 文件处理器
    ├── docx_handle.py        # DOCX 文件处理器 (python-docx)
    ├── doc_handle.py         # DOC 文件处理器 (win32com / textract / python-docx)
    ├── csv_handle.py         # CSV 文件处理器
    ├── json_handle.py        # JSON 文件处理器
    └── yaml_handle.py        # YAML 文件处理器
```

---

## 数据流

```
文件（目录 / 指定路径）
        │
        ▼
  FileReader.read_files()
        │  List[Document]    ← 每个 Document 含原始文本 + 元数据(file_type/file_size/hash等)
        ▼
  ChineseTextChunker.chunk_document(doc)
        │  List[Chunk]       ← 每个 Chunk 含 chunk_id / doc_id / content
        ▼
  DocumentProcessor.process()   ← 封装读写+分块，一步到位
        │  List[Chunk]
        ▼
  下游使用（向量化、检索、索引等）
```

---

## 核心数据类（models.py）

**`Document`** — 原始文件元数据 + 文本内容：

| 字段 | 类型 | 说明 |
|---|---|---|
| `file_name` | `str` | 文件路径（传入的原始路径） |
| `file_type` | `FileType` | 文件类型枚举 |
| `file_path` | `str` | 文件名（`os.path.basename` 结果） |
| `file_size` | `int` | 文件大小（字节） |
| `file_content` | `str` | 文件文本内容 |
| `status` | `str` | `"success"` 或 `"failed"` |
| `file_hash` | `str` | 内容 SHA256（自动计算） |

**`Chunk`** — 分块后的文本片段，记录来源和序号：

| 字段 | 类型 | 说明 |
|---|---|---|
| `chunk_id` | `str` | 唯一标识，如 `"test.pdf_chunk_0"` |
| `doc_id` | `str` | 来源文档（Document 的 file_name） |
| `content` | `str` | 分块文本内容 |

---

## 1. handle/ — 格式处理器

每种格式对应一个 Handler，统一继承 `BaseFileHandler`，实现 `process(file: str) -> Document`。

| 扩展名 | Handler | 依赖库 | 编码处理 |
|---|---|---|---|
| `.txt` | `TxtFileHandler` | — | UTF-8，失败后自动检测编码（chardet） |
| `.pdf` | `PdfFileHandler` | PyPDF2 | 逐页提取 |
| `.md` | `MarkdownFileHandler` | — | UTF-8 |
| `.docx` | `DocxFileHandler` | python-docx | 读取段落文本 |
| `.doc` | `DocFileHandler` | win32com / textract / python-docx | 三种降级策略 |
| `.csv` | `CsvFileHandler` | — | UTF-8，失败后自动检测编码 |
| `.json` | `JsonFileHandler` | — | 解析后格式化为带缩进的字符串 |
| `.yaml` / `.yml` | `YamlFileHandler` | PyYAML | 解析后重新 dump 为字符串 |

---

## 2. file_reader.py — 文件读取器

遍历目录或处理指定文件，按扩展名分发到对应 Handler。

```python
from file_reader import FileReader

# 初始化（directory_path 可选）
reader = FileReader()

# ── 扫描目录 ──
reader.read_files(directory_path="data/test")
reader.read_files(directory_path="data/test", file_extensions=[".md"])
reader.read_files(directory_path="data/test", recursive=False)

# ── 处理指定文件 ──
reader.read_files(file_paths="report.pdf")
reader.read_files(file_paths=["a.txt", "b.md", "c.pdf"])
```

**返回**: `List[Document]`

---

## 3. text_chunker.py — 中文文本分块器

基于 HanLP 分词的中文文本滑动窗口分块，支持块间重叠。

```python
from text_chunker import ChineseTextChunker
from models import Document

chunker = ChineseTextChunker(chunk_size=500, overlap=100)

# 从 Document 分块
doc = Document(file_name="test.txt", ..., file_content="长文本内容...")
chunks: list[Chunk] = chunker.chunk_document(doc)
# chunks[0].chunk_id  → "test.txt_chunk_0"
# chunks[0].doc_id     → "test.txt"
# chunks[0].content    → "文本内容..."

# 批量处理（自动跳过 failed 文档）
chunker.chunk_documents([doc1, doc2, doc3])
```

**分块策略：**
1. 超长文本（>500KB）先按段落预分割
2. 每个段落用 HanLP 分词得到 token 序列
3. 滑动窗口切分，窗口大小 = `chunk_size` tokens
4. 相邻窗口重叠 = `overlap` tokens
5. 窗口边界尽量对齐到句子结束位置

---

## 4. document_processor.py — 文档处理器（高层接口）

整合 `FileReader` + `ChineseTextChunker`，一次调用完成读取 → 分块。

```python
from document_processor import DocumentProcessor

processor = DocumentProcessor()

# ── 扫描目录并分块 ──
chunks = processor.process(directory_path="data/test")

# ── 处理指定文件并分块 ──
chunks = processor.process(file_paths="report.pdf")
chunks = processor.process(file_paths=["a.txt", "b.md"])

# ── 仅统计 ──
stats = processor.get_file_stats(directory_path="data/test")
```

**参数和 FileReader.read_files 完全一致**：
- `file_extensions` — 按扩展名过滤
- `recursive` — 是否递归子目录
- `file_paths` — 指定文件路径
- `directory_path` — 扫描目录

**返回**: `List[Chunk]`

---

## 使用场景

### 扫描目录处理
```python
reader = FileReader()
docs = reader.read_files(directory_path="data/test")
# → [Document, Document, ...]

chunker = ChineseTextChunker()
chunks = chunker.chunk_documents(docs)
# → [Chunk, Chunk, ...]
```

### 一步到位
```python
processor = DocumentProcessor()
chunks = processor.process(directory_path="data/test")
# → [Chunk, Chunk, ...]  含 chunk_id / doc_id / content
```

### 上传单文件
```python
reader = FileReader()
docs = reader.read_files(file_paths="uploaded.pdf")
# → [Document]
```

---

## 扩展：添加新的文件格式

1. 在 `handle/` 下新建 `xxx_handle.py`，继承 `BaseFileHandler`
2. 实现 `process(self, file: str) -> Document` 方法
3. 在 `handle/__init__.py` 中注册
4. 在 `file_reader.py` 的 `_handlers` 字典中添加扩展名映射

```python
# handle/xxx_handle.py
from ..models import Document, FileType
from .base_handle import BaseFileHandler

class XxxFileHandler(BaseFileHandler):
    def process(self, file: str) -> Document:
        # ... 读取逻辑 ...
        return Document(
            file_name=file,
            file_type=FileType.TXT,
            file_path=os.path.basename(file),
            file_size=os.path.getsize(file),
            file_content=content,
            status="success",
        )
```
