"""前端共享常量"""

AGENT_OPTIONS = {
    "naive_rag_agent": "标准 RAG",
    "local_search_agent": "知识图谱搜索",
}

AGENT_DESCRIPTIONS = {
    "naive_rag_agent": "基于知识库向量检索，快速生成诊断建议",
    "local_search_agent": "基于 Neo4j 图谱实体与关系，深度关联检索",
}

EQUIPMENT_TYPES = ["未指定", "数控机床", "工业机器人", "PLC 控制系统", "液压系统", "变频器", "其他"]

FAULT_SEVERITY_LEVELS = ["未指定", "低 — 可继续运行", "中 — 需尽快处理", "高 — 建议停线检修"]

EXAMPLE_QUESTIONS = [
    "设备运行中突然停机，可能的原因有哪些？",
    "如何排查电机过热故障？",
    "PLC 通讯中断怎么处理？",
    "液压系统压力不足，故障排查步骤",
    "变频器过流报警的常见原因",
]

QUICK_FAULT_TAGS = [
    "突然停机",
    "电机过热",
    "通讯中断",
    "压力不足",
    "过流报警",
]
