"""前端共享常量"""

from backend.agents import AGENT_REGISTRY

AGENT_OPTIONS = {
    "general_agent": "通用问答",
    "intent_rag_agent": "知识库问答",
}

AGENT_DESCRIPTIONS = {
    key: entry["description"]
    for key, entry in AGENT_REGISTRY.items()
    if entry.get("description")
}



QUICK_QUESTION = [
    "设备运行中突然停机，可能的原因有哪些？",
    "如何排查电机过热故障？",
    "PLC 通讯中断怎么处理？",
    "液压系统压力不足，故障排查步骤",
    "变频器过流报警的常见原因",
]

