"""
图谱构建与社区摘要提示模板集合。

这些模板用于图谱索引的构建与维护流程。
"""

system_template_build_graph = """
-目标-
给定相关的文本文档和实体类型列表，从文本中识别出这些类型的所有实体以及所识别实体之间的所有关系。

-步骤-
1. 识别所有实体。对于每个已识别的实体，提取以下信息：
   - entity_name：实体名称
   - entity_type：以下类型之一：[{entity_types}]
   - entity_description：对实体属性和活动的综合描述
   格式：("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. 从步骤1中识别的实体中，识别彼此相关的所有实体配对，提取：
   - source_entity：源实体名称
   - target_entity：目标实体名称
   - relationship_type：以下类型之一：[{relationship_types}]，不能归类时使用"其它"
   - relationship_description：关系解释
   - relationship_strength：关系强度评分
   格式：("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_type>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. 所有实体和关系用中文输出，使用{record_delimiter}作为分隔符。
4. 完成后输出{completion_delimiter}。
"""

human_template_build_graph = """
-真实数据-
######################
实体类型：{entity_types}
关系类型：{relationship_types}
文本：{input_text}
######################
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
    "system_template_build_graph",
    "human_template_build_graph",
    "system_template_build_index",
    "user_template_build_index",
    "community_template",
    "COMMUNITY_SUMMARY_PROMPT",
    "entity_alignment_prompt",
]
