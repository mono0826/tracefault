import os
import sys
from pathlib import Path
from typing import List

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 离线模式：模型已缓存时跳过联网检查（国内 huggingface 连不上也不影响）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
# 屏蔽 transformers / huggingface 的杂音警告
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer

from backend.config.settings import OPENAI_LLM_CONFIG, EMBEDDING_MODEL, EMBEDDING_DEVICE


class _SentenceTransformerAdapter:
    """包装 SentenceTransformer，提供 embed_query / embed_documents 接口"""

    def __init__(self, model_name: str, device: str = "cpu"):
        # 优先离线加载（本地已缓存时跳过联网检查），失败则回退在线加载
        try:
            self._model = SentenceTransformer(model_name, device=device, local_files_only=True)
        except Exception:
            self._model = SentenceTransformer(model_name, device=device)
        self._model.encode("warmup", show_progress_bar=False)

    def embed_query(self, text: str) -> List[float]:
        return self._model.encode(text, show_progress_bar=False).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embs = self._model.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embs]



_embedding_model = None


def get_embeddings_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    _embedding_model = _SentenceTransformerAdapter(EMBEDDING_MODEL, device=EMBEDDING_DEVICE)
    print(f"[embedding_worker] Model loaded: {EMBEDDING_MODEL}")
    return _embedding_model


def get_llm_model():
    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    return ChatOpenAI(**config)


def get_stream_llm_model():
    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    config["streaming"] = True
    return ChatOpenAI(**config)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    chinese = len([c for c in text if "一" <= c <= "鿿"])
    english = len(text) - chinese
    return chinese + english // 4


if __name__ == "__main__":
    # ---- 测试 LLM ----
    print("=" * 50)
    print("测试 LLM")
    print("=" * 50)
    llm = get_llm_model()
    resp = llm.invoke("你好")
    print(f"LLM 响应: {resp}")
    assert resp.content, "LLM 返回内容为空"
    print("  ✓ LLM 调用成功\n")

    # ---- 测试 Embedding ----
    print("=" * 50)
    print("测试 Embedding 适配器")
    print("=" * 50)
    emb = get_embeddings_model()

    # 1. embed_query 单条
    vec = emb.embed_query("主轴温度异常升高")
    assert isinstance(vec, list), "embed_query 返回值不是 list"
    assert all(isinstance(v, float) for v in vec), "embed_query 元素不是 float"
    print(f"  ✓ embed_query: dim={len(vec)}, 前5维={vec[:5]}")

    # 2. embed_documents 批量
    texts = ["冷却液流量不足", "水垢沉积", "主轴过热"]
    vecs = emb.embed_documents(texts)
    assert len(vecs) == 3, f"embed_documents 返回数量不对: {len(vecs)} vs 3"
    assert all(len(v) == len(vec) for v in vecs), "embed_documents 维度不一致"
    print(f"  ✓ embed_documents: {len(vecs)} 条, dim={len(vecs[0])}")

    # 3. 缓存命中
    emb2 = get_embeddings_model()
    assert emb2 is emb, "get_embeddings_model 缓存失效"
    print("  ✓ 单例缓存: 同一实例\n")
