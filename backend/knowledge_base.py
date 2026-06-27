"""知识库引擎 — 文档处理、向量存储、语义搜索"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import faiss
import numpy as np

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.pipelines.file_reader import FileReader
from backend.config.settings import (
    EMBEDDING_DEVICE,
    EMBEDDING_MODEL,
    VECTOR_STORE_PATH,
    PROJECT_ROOT,
)
from backend.models.get_models import get_embeddings_model

# ---------- 路径 ----------
DB_PATH = PROJECT_ROOT / "data" / "equipment_fault_qa.db"
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"
VECTOR_DIR = Path(str(VECTOR_STORE_PATH))
VECTOR_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

FAISS_INDEX_PATH = VECTOR_DIR / "faiss.index"
CHUNK_META_PATH = VECTOR_DIR / "chunks_meta.json"


# ---------- 数据库 ----------
def _get_db():
    conn = __import__("sqlite3").connect(str(DB_PATH))
    conn.row_factory = __import__("sqlite3").Row
    return conn


def _init_vector_store():
    """读取已有向量存储（不加载模型）"""
    if FAISS_INDEX_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            chunk_meta = json.load(f)
        return index, chunk_meta
    # 索引不存在时返回空，由 process_and_store_document 创建
    return None, []


def _save_vector_store(index, chunk_meta):
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    with open(CHUNK_META_PATH, "w", encoding="utf-8") as f:
        json.dump(chunk_meta, f, ensure_ascii=False, indent=2)


# ---------- 核心接口 ----------

def process_and_store_document(file_path: str) -> dict:
    """处理单个文档：读取 → 分块 → 向量化 → 存储

    Args:
        file_path: 上传文件保存后的绝对路径

    Returns:
        dict: 处理结果统计
    """
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    print(f"[知识库] 开始处理: {filename}")

    # 1. 用 FileReader 直接读单个文件
    reader = FileReader()
    docs = reader.read_files(file_paths=file_path)
    if not docs or docs[0].status == "failed":
        return {"status": "failed", "message": "文件解析失败", "chunk_count": 0}

    target = docs[0]

    # 2. 用 ChineseTextChunker 分块
    from backend.pipelines.text_chunker import ChineseTextChunker

    chunker = ChineseTextChunker()
    chunks = chunker.chunk_document(target)
    if not chunks:
        return {"status": "failed", "message": "分块结果为空", "chunk_count": 0}

    # 3. 向量化
    model = get_embeddings_model()
    index, chunk_meta = _init_vector_store()
    if index is None:
        dim = model.get_sentence_embedding_dimension()
        index = faiss.IndexFlatIP(dim)
        chunk_meta = []

    texts = [c.content for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False).astype(np.float32)

    # 4. 写入 FAISS + 元数据
    start_id = len(chunk_meta)
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        chunk_meta.append({
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "content": chunk.content,
            "vector_id": start_id + i,
        })

    index.add(embeddings)
    _save_vector_store(index, chunk_meta)

    print(f"[知识库] 完成: {filename} -> {len(texts)} 个 Chunk")
    return {
        "status": "success",
        "filename": filename,
        "chunk_count": len(texts),
        "total_chunks": len(chunk_meta),
    }


def search_chunks(query: str, top_k: int = 5) -> List[dict]:
    """语义搜索最相关的 Chunk"""
    index, chunk_meta = _init_vector_store()
    if index is None or index.ntotal == 0:
        return []

    model = get_embeddings_model()
    query_vec = model.encode([query], show_progress_bar=False).astype(np.float32)

    scores, indices = index.search(query_vec, min(top_k, index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunk_meta):
            continue
        meta = chunk_meta[idx]
        results.append({
            "chunk_id": meta["chunk_id"],
            "doc_id": meta["doc_id"],
            "content": meta["content"],
            "score": float(score),
        })
    return results


def get_knowledge_stats() -> dict:
    """获取知识库统计信息"""
    index, chunk_meta = _init_vector_store()
    return {
        "documents": len(set(m["doc_id"] for m in chunk_meta)),
        "chunks": len(chunk_meta),
        "vector_dim": index.d if index is not None and index.ntotal > 0 else 0,
    }


def list_documents() -> List[dict]:
    """列出已处理文档"""
    index, chunk_meta = _init_vector_store()
    seen = {}
    for m in chunk_meta:
        did = m["doc_id"]
        if did not in seen:
            seen[did] = {"title": did, "source_file": did}
    return list(seen.values())
