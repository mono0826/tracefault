"""
图谱构建与社区摘要提示模板集合。

这些模板用于图谱索引的构建与维护流程。
"""

tuple_delimiter = " : "
record_delimiter = "\n"
completion_delimiter = "\n\n"

entity_types = [
    "设备",
    "部件",
    "故障",
    "故障原因",
    "故障现象",
    "维修措施",
    "参数",
]

relationship_types = [
    "发生",
    "包含",
    "导致",
    "表现为",
    "维修解决",
    "关联于",
]

system_template_build_graph = f"""
你是设备故障知识图谱抽取专家，一次性完成实体、关系提取。
仅能使用给定的实体类型、关系类型，禁止自创类型。
同义实体只保留一个标准实体，不重复新建节点。

命名一致性要求：
- 同一实体在不同句子中出现时，必须使用完全相同的名称，不得使用同义词、简称或不同表述。
- 例如："数控加工中心主轴"和"加工中心主轴"应统一为同一个标准名称。
- 避免使用代词（它、该设备、此部件等），始终显式写出实体全称。

实体提取原则：
- 只提取在文本中明确出现、语义清晰的实体，禁止自行推断或创造实体。
- 如果某个实体在文本中表述模糊、指代不明或缺乏确定性描述，则不应提取。
- 不确定的实体宁可不提取，也不要随意命名或归类。
- 实体名称必须是**名词性短语**，不能包含动作动词（如"维修""更换""清洗"等）。
- 动作应通过关系类型来表达，不要将动作嵌入实体名称中。
- 例如："主轴冷却系统维修"是错误的实体名，应表示为实体"主轴冷却系统" + 关系"维修解决"。

置信度要求：
- 为每个提取的实体和关系输出一个置信度分数，范围 0.0~1.0。
- 分数含义：1.0=完全确定，0.8=高置信度，0.6=中等置信度，0.0~0.4=低置信度。
- 文本中明确出现、描述清晰的实体给 0.8~1.0。
- 文本中虽未直接出现但能从上下文明确推断出的实体给 0.6~0.8。
- 不确定是否应该提取的实体给 0.0~0.4，这类宁可不提取。

输出格式：
1.实体格式：(entity{tuple_delimiter}实体名称{tuple_delimiter}实体类型{tuple_delimiter}实体描述{tuple_delimiter}置信度)
2.关系格式：(relationship{tuple_delimiter}源实体{tuple_delimiter}目标实体{tuple_delimiter}关系类型{tuple_delimiter}关系描述{tuple_delimiter}置信度)
"""

human_template_build_graph = f"""
实体类型列表：{entity_types}
关系类型列表：{relationship_types}
待解析文本：{{input_text}}
输出：
"""

system_template_build_index = """
你是一名数据处理助理。您的任务是识别列表中的重复实体，并决定应合并哪些实体。
这些实体在格式或内容上可能略有不同，但本质上指的是同一个实体。运用你的分析技能来确定重复的实体。
以下是识别重复实体的规则：
1.语义上差异较小的实体应被视为重复。
2.格式不同但内容相同的实体应被视为重复。
3.引用同一现实世界对象或概念的实体，即使描述不同，也应被视为重复。
4.如果它指的是不同的数字、日期或产品型号，请不要合并实体。
输出格式：
1.将要合并的实体输出为Python列表的格式，输出时保持它们输入时的原文。
2.如果有多组可以合并的实体，每组输出为一个单独的列表，每组分开输出为一行。
3.如果没有要合并的实体，就输出一个空的列表。
4.只输出列表即可，不需要其它的说明。
5.不要输出嵌套的列表，只输出列表。
######################
-示例-
######################
示例1：
['Star Ocean The Second Story R', 'Star Ocean: The Second Story R', 'Star Ocean: A Research Journey']
#############
输出：
['Star Ocean The Second Story R', 'Star Ocean: The Second Story R']
#############################
示例2：
['Sony', 'Sony Inc', 'Google', 'Google Inc', 'OpenAI']
#############
输出：
['Sony', 'Sony Inc']
['Google', 'Google Inc']
#############################
示例3：
['December 16, 2023', 'December 2, 2023', 'December 23, 2023', 'December 26, 2023']
输出：
[]
#############################
"""

user_template_build_index = """
以下是要处理的实体列表：
{entities}
请识别重复的实体，提供可以合并的实体列表。
输出：
"""

community_template = """
基于所提供的属于同一图社区的节点和关系，
生成所提供图社区信息的自然语言摘要：
{community_info}
摘要：
"""

COMMUNITY_SUMMARY_PROMPT = """
给定一个输入三元组，生成信息摘要。没有序言。
"""

entity_alignment_prompt = """
Given these entities that should refer to the same concept:
{entity_desc}

Which entity ID best represents the canonical form? Reply with only the entity ID."""

__all__ = [
    "tuple_delimiter",
    "record_delimiter",
    "completion_delimiter",
    "entity_types",
    "relationship_types",
    "system_template_build_graph",
    "human_template_build_graph",
    "system_template_build_index",
    "user_template_build_index",
    "community_template",
    "COMMUNITY_SUMMARY_PROMPT",
    "entity_alignment_prompt",
]
