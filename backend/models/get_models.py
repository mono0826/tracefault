import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 屏蔽 transformers / huggingface 的杂音警告
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from langchain_openai import ChatOpenAI

from backend.config.settings import OPENAI_LLM_CONFIG, EMBEDDING_MODEL, EMBEDDING_DEVICE   


_embedding_model = None

def get_embeddings_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    from sentence_transformers import SentenceTransformer
    _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=EMBEDDING_DEVICE)
    _embedding_model.encode("warmup", show_progress_bar=False)
    print(f"[embedding_worker] Model loaded: {EMBEDDING_MODEL}", flush=True)
    return _embedding_model

def _get_cached_embedding():
    """检查模型是否已加载（供外部使用）"""
    from sentence_transformers import SentenceTransformer
    global _embedding_model
    return _embedding_model


def get_llm_model():
    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    return ChatOpenAI(**config)

def get_stream_llm_model():
    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    config["streaming"] = True
    return ChatOpenAI(**config)


def count_tokens(text: str) -> int:
    """简单通用的 token 计数"""
    if not text:
        return 0

    # 粗略估算（中文字符 ≈ 1 token，英文 ≈ 0.25 token）
    chinese = len([c for c in text if "一" <= c <= "鿿"])
    english = len(text) - chinese
    return chinese + english // 4


if __name__ == "__main__":
    # 测试 LLM
    llm = get_llm_model()
    print(llm.invoke("你好"))

    # 测试流式 LLM
    llm_stream = get_stream_llm_model()
    print("流式输出:")
    for chunk in llm_stream.stream("你好"):
        print(chunk.content, end="")
    print()

    # 测试 embedding
    test_text = "你好，这是一个测试。"
    embeddings = get_embeddings_model()
    vectors = embeddings.encode(test_text, show_progress_bar=False).tolist()
    print(vectors)

    # 测试 token 计数
    test_text = "Hello 你好世界"
    tokens = count_tokens(test_text)
    print(f"Token计数: '{test_text}' = {tokens} tokens")
