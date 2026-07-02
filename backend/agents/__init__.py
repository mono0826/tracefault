from .general_agent import GeneralAgent
from .rag_agent import RAGAgent

# 单例 & 便捷别名（供前端 from backend.agents import ...）
general_agent = GeneralAgent()
chat = general_agent.chat
chat_stream = general_agent.chat_stream

rag_agent = RAGAgent()
intent_rag = rag_agent.intent_rag
intent_rag_stream = rag_agent.intent_rag_stream

AGENT_REGISTRY = {
    "general_agent": {
        "fn": chat,
        "stream_fn": chat_stream,
        "description": "通用对话，不检索知识图谱",
    },
    "intent_rag_agent": {
        "fn": intent_rag,
        "stream_fn": intent_rag_stream,
        "description": "先识别意图并改写问题，再检索回答",
    },
}