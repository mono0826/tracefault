# Search 模块

## 目录结构

```
backend/search/
├── __init__.py                  # 模块初始化，导出搜索类和工具类
├── local_search.py              # 本地搜索 — 基于向量检索的社区内精确查询
├── global_search.py             # 全局搜索 — 基于 Map-Reduce 的跨社区查询
├── retrieval_adapter.py         # 检索结果适配器，统一转换为 RetrievalResult 格式
├── utils.py                     # 向量工具，提供余弦相似度计算和向量排序
├── tool_registry.py             # 工具注册表，集中管理所有搜索工具类
└── tool/                        # 搜索工具集合
    ├── __init__.py
    ├── base.py                  # BaseSearchTool 基类
    ├── local_search_tool.py     # 本地搜索工具封装
    ├── global_search_tool.py    # 全局搜索工具封装
    ├── hybrid_tool.py           # 混合搜索工具（结合局部和全局）
    ├── naive_search_tool.py     # 简单向量搜索工具
    ├── deep_research_tool.py    # 深度研究工具（多步思考-搜索-推理）
    ├── deeper_research_tool.py  # 增强版深度研究（社区感知 + 图谱分析）
    ├── chain_exploration_tool.py # 链式探索工具（图谱路径探索）
    ├── hypothesis_tool.py       # 假设生成工具（多角度分析）
    ├── validation_tool.py       # 答案验证工具
    ├── deeper_research/         # 增强版深度研究辅助模块
    │   ├── __init__.py
    │   ├── enhancer.py          # CoE 增强搜索
    │   └── branching.py         # 分支推理（多分支创建、矛盾检测、引用生成）
    └── reasoning/               # 推理组件
        ├── __init__.py
        ├── search.py            # 推理搜索（DualPathSearcher、QueryGenerator）
        ├── thinking.py          # ThinkingEngine 思考引擎
        ├── prompts.py           # 提示模板工具
        ├── nlp.py               # NLP 工具函数
        ├── validator.py         # AnswerValidator 答案验证器
        ├── community_enhance.py # CommunityAwareSearchEnhancer
        ├── kg_builder.py        # DynamicKnowledgeGraphBuilder
        ├── evidence.py          # EvidenceChainTracker 证据链追踪
        └── chain_of_exploration.py # Chain of Exploration 搜索实现
```

## 模块说明

Search 模块提供多种搜索策略，通过知识图谱（Neo4j）、向量检索和 LLM 结合，实现高效的知识检索和问答。模块采用分层架构，从基础搜索到高级推理逐层封装。

```
                    ┌─────────────────────┐
                    │    BaseSearchTool    │ ← 共享：缓存、连接、向量搜索
                    └────────┬────────────┘
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
 LocalSearchTool   GlobalSearchTool    HybridSearchTool
 (历史感知 RAG)    (Map-Reduce)       (低级+高级融合)
         │                  │
         └────────┬─────────┘
                  ▼
         NaiveSearchTool ← 纯向量兜底
                  │
                  ▼
         DeepResearchTool
         (多轮思考-搜索-推理)
                  │
                  ▼
         DeeperResearchTool
         (社区感知 + 动态图谱 + CoE + 证据链)
```

---

## 一、基础搜索层（非 Tool，可直接使用）

### LocalSearch — 本地搜索（局部向量检索）

**文件**: `local_search.py`

基于 Neo4j 向量索引的社区内精确搜索：

1. 对查询文本做嵌入（embedding）
2. 在 Neo4j `vector` 索引上做相似度搜索，找到最相关的 `__Entity__` 节点
3. 一条 Cypher 查询同时拉取五类关联信息：
   - **Chunks** — 提到该实体的原文片段
   - **Reports** — 实体所属 `__Community__` 的摘要
   - **Outside Relationships** — 实体向外的关联描述
   - **Inside Relationships** — 实体间的内部关联
   - **Entities** — 实体自身描述
4. 将上述信息组装为上下文传给 LLM 生成答案

**适用场景**: "轴承磨损有哪些检测方法？" — 明确具体问题，需在特定实体附近精确检索。

```python
from backend.search.local_search import LocalSearch
local_search = LocalSearch(llm, embeddings)
result = local_search.search("轴承磨损检测方法")
```

---

### GlobalSearch — 全局搜索（Map-Reduce）

**文件**: `global_search.py`

借鉴 Map-Reduce 模式，面向整个知识图谱的广泛搜索：

1. **Map 阶段**: 查询指定层级的 `__Community__` 节点，对每个社区调用 LLM 提取与问题相关的信息
2. **Reduce 阶段**: 将所有中间结果合并，调用 LLM 生成最终综合答案

**适用场景**: "常见的设备故障类型有哪些？" — 宽泛概念性问题，需跨多个主题社区整合知识。

```python
from backend.search.global_search import GlobalSearch
global_search = GlobalSearch(llm)
result = global_search.search("常见的设备故障类型", level=0)
```

---

## 二、工具封装层（继承 BaseSearchTool，提供完整工具链）

所有工具继承 `BaseSearchTool`（`tool/base.py`），共享以下能力：
- **缓存管理**: `CacheManager` + `MemoryCacheBackend`，支持上下文和关键词感知的缓存键
- **性能监控**: 记录 query_time、llm_time、total_time
- **Neo4j 连接**: 同时提供 `graph`（Neo4jGraph）和 `driver`（直接执行查询）
- **通用检索方法**: `vector_search()`（向量搜索）、`text_search()`（文本匹配兜底）、`semantic_search()`（语义重排序）、`filter_by_relevance()`（相关性过滤）
- **LangChain Tool 封装**: `get_tool()` 返回 `BaseTool` 实例，可直接集成到 LangChain Agent

### LocalSearchTool — 本地搜索工具

**文件**: `tool/local_search_tool.py`

在 `LocalSearch` 基础上增加完整 RAG 链：
- **历史感知检索器**: 通过 `create_history_aware_retriever` 支持多轮对话，自动理解上下文指代
- **问答链**: 通过 `create_stuff_documents_chain` 将检索结果注入 LLM
- **关键词提取**: 调用 LLM 提取 `low_level` / `high_level` 关键词
- **结构化输出**: `structured_search()` 返回 `answer` + `retrieval_results`（标准化 `RetrievalResult` 列表） + `raw_context`
- **两种 Tool 形态**: `get_tool()` 返回 Retriever 工具，`get_structured_tool()` 返回结构化工具

---

### GlobalSearchTool — 全局搜索工具

**文件**: `tool/global_search_tool.py`

在 `GlobalSearch` 基础上增加：
- **关键词过滤**: LLM 提取关键词，在 Cypher 中用 `CONTAINS` 过滤社区数据
- **批处理**: 社区分批次处理，减少 LLM 调用次数
- **社区排序**: 按 `community_rank` 和 `weight` 降序，优先处理高价值社区
- **结构化输出**: 返回 `intermediate_results`（Map 结果） + `final_answer`（Reduce 答案） + `retrieval_results`

---

### HybridSearchTool — 混合搜索工具（类似 LightRAG）

**文件**: `tool/hybrid_tool.py`

同时检索低级（实体/关系）和高级（社区/主题）内容，合并后让 LLM 综合回答。

**低级检索**（`_retrieve_low_level_content`）:
1. 用关键词或向量搜索找到相关 `__Entity__`
2. 三路独立 Cypher 查询 — entity_query（实体描述）、relation_query（实体间关系）、chunk_query（关联文本块）
3. 回退机制: 关键词搜索 → 向量搜索 → 文本匹配

**高级检索**（`_retrieve_high_level_content`）:
1. 按关键词过滤指定层级的 `__Community__`
2. 返回社区摘要作为主题概念

**合并**: `merge_retrieval_results()` 按 `(source_id, granularity)` 去重，保留高分结果。

**适用场景**: "电机过热故障可能的原因及解决方案" — 既需要具体实体数据，又需要主题概念。

```python
HybridTool = get_tool_class("hybrid_search")
hybrid = HybridTool()
result = hybrid.search("电机过热故障原因")
```

---

### NaiveSearchTool — 简单向量搜索工具

**文件**: `tool/naive_search_tool.py`

最简实现，纯粹基于 embedding 相似度：
1. 查询做嵌入
2. 获取所有带 embedding 的 `__Chunk__`（限制 100 候选）
3. `VectorUtils.rank_by_similarity()` 批量余弦相似度排序
4. 取 top_k 作为上下文传给 LLM

**设计意图**: 备选方案。`__Chunk__` 节点直接在 Neo4j 内做向量化，不需要额外向量数据库。

**关键词提取**: 返回空字典（naive 不需要关键词）。

**适用场景**: 快速兜底搜索，或简单事实性查询。

---

### DeepResearchTool — 深度研究工具

**文件**: `tool/deep_research_tool.py`

**核心**: 多轮迭代的 **思考 → 搜索 → 推理** 循环（类似 ReAct 模式）。

流程:
1. **问题分解**: `QueryGenerator` 将原始问题拆解为多个子查询
2. **初始化思考引擎**: 将子查询计划记录到 `ThinkingEngine`
3. **多轮迭代**（最多 `MAX_SEARCH_LIMIT` 轮）:
   - 首轮使用预生成子查询，后续轮用 LLM 生成的下一步查询
   - 检查查询是否重复执行（`has_executed_query`）
   - 执行 **双路搜索**（`DualPathSearcher`）:
     - **知识库路**（KB）: `LocalSearchTool` 搜索本地内容
     - **知识图谱路**（KG）: `GlobalSearchTool` 搜索社区
   - LLM 从搜索结果中提取有用信息（`RELEVANT_EXTRACTION_PROMPT`）
   - 积累有用信息到 `all_retrieved_info`
   - 评估是否需要继续生成跟进查询
4. 生成最终答案（含思考过程）

**关键组件**:
- `ThinkingEngine` — 管理多轮推理消息历史，支持标签标记
- `DualPathSearcher` — 知识库 + 知识图谱双路并行
- `AnswerValidator` — 验证答案质量，低质量不缓存

**流式支持**: `thinking_stream()` / `search_stream()` 可逐段输出思考过程。

**适用场景**: "分析这台设备的故障历史，找出可能的根本原因并给出预防建议" — 需多轮推理和多角度搜索的复杂问题。

```python
tool = DeepResearchTool()
result = tool.search("压缩机连续三次故障的根本原因是什么")
```

---

### DeeperResearchTool — 增强版深度研究工具

**文件**: `tool/deeper_research_tool.py`

`DeepResearchTool` 的全面增强版，整合四种额外能力:

| 组件 | 来源 | 作用 |
|------|------|------|
| `CommunityAwareSearchEnhancer` | `reasoning/community_enhance.py` | 搜索前分析相关知识社区，获取摘要和后续查询策略 |
| `DynamicKnowledgeGraphBuilder` | `reasoning/kg_builder.py` | 从检索结果中实时提取实体关系，构建查询子图 |
| `ChainOfExplorationSearcher` | `reasoning/chain_of_exploration.py` | 从起始实体出发，沿关系链多步探索间接关联 |
| `EvidenceChainTracker` | `reasoning/evidence.py` | 记录推理步骤的证据来源，矛盾检测，可信度评估 |

完整流程:

1. **问题分解**（同 `DeepResearchTool`）
2. **社区感知**: `enhance_search_with_coe` 分析社区获取上下文、关注实体和跟进查询
3. **构建知识图谱**: 提取实体构建子图，识别核心实体
4. **Chain of Exploration**: 从核心实体出发沿关系探索，发现路径和间接关联
5. **多假设分支推理**: 对复杂问题（`complexity > 0.7`）生成多个假设，创建独立推理分支
6. **迭代搜索**: 同 `DeepResearchTool`，但每次搜索前做 CoE 增强
7. **矛盾检测**: 数值矛盾（同一实体在不同来源数值不同）和语义矛盾
8. **分支合并**: 合并多个推理分支的结果
9. **增强答案生成**: 最终提示融合知识图谱结构、社区见解、探索路径、矛盾分析

**适用场景**: "某型号压缩机连续三次出现相同故障的根本原因是什么？给出维修建议和预防措施。" — 最复杂的分析问题。

```python
tool = DeeperResearchTool()
result = tool.search("压缩机连续三次故障的根本原因")
```

---

## 三、专用工具（不继承 BaseSearchTool）

### ChainOfExplorationTool — 链式探索工具

**文件**: `tool/chain_exploration_tool.py`

封装 `ChainOfExplorationSearcher`，核心方法 `explore(query, start_entities)`:
1. 从起始实体出发
2. 每步找出邻居节点，用 embedding 计算与查询的相关性
3. LLM 决定下一步探索方向
4. 记录探索路径和发现的实体/关系/内容
5. 返回标准化的 `RetrievalResult`

**适用场景**: 已知部分相关实体，需沿图谱关系链发现更多间接关联。

```python
from backend.search.tool_registry import create_extra_tool
coe_tool = create_extra_tool("chain_exploration")
result = coe_tool.explore("故障原因", start_entities=["轴承", "电机"])
```

---

### HypothesisGeneratorTool — 假设生成工具

**文件**: `tool/hypothesis_tool.py`

极简封装，调用 `QueryGenerator.generate_multiple_hypotheses()` 对复杂问题生成 2-3 个可能假设，辅助多分支推理。

```python
hypothesis_tool = create_extra_tool("hypothesis_generator")
hypotheses = hypothesis_tool.generate("导致电机过热的原因有哪些？")
# → ["散热系统故障导致过热", "过载运行导致过热", "轴承润滑不良导致摩擦过热"]
```

---

### AnswerValidationTool — 答案验证工具

**文件**: `tool/validation_tool.py`

基于关键词和错误模式检测评估答案质量:
- **长度检查**: 答案是否过短
- **相关性**: 关键词匹配判断是否覆盖问题核心
- **错误模式检测**: 检测常见错误模式（如"很抱歉"、"我不确定"等）

```python
validator_tool = create_extra_tool("answer_validator")
validation = validator_tool.validate("电机过热原因", answer)
# → {"query": ..., "answer": ..., "validation": {"passed": True/False, ...}}
```

---

## 四、核心函数

- `LocalSearch.as_retriever()` — 构建 Neo4j 向量检索器
- `GlobalSearch.search(query, level)` — Map-Reduce 全局搜索
- `tool_registry.get_tool_class(name)` — 按名称获取注册的搜索工具类
- `tool_registry.create_extra_tool(name)` — 按名称创建专用工具实例
- `retrieval_adapter.results_from_documents()` — LangChain Documents 转 `RetrievalResult`
- `retrieval_adapter.merge_retrieval_results()` — 合并多组检索结果并去重
- `retrieval_adapter.results_to_payload()` — `RetrievalResult` 列表转可序列化 payload
- `VectorUtils.cosine_similarity()` — 计算向量余弦相似度
- `VectorUtils.batch_cosine_similarity()` — 批量计算向量相似度
- `VectorUtils.rank_by_similarity()` — 按相似度排序实体列表
- `VectorUtils.filter_documents_by_relevance()` — 按相关性过滤文档

## 五、使用场景速查

| 工具 | 难度 | 适用场景 |
|------|------|---------|
| `LocalSearchTool` | ⭐ | 明确问题的精确搜索，快速定位社区内内容 |
| `GlobalSearchTool` | ⭐⭐ | 概念性问题，需跨社区整合知识 |
| `HybridSearchTool` | ⭐⭐ | 需同时了解具体实体和高级概念 |
| `NaiveSearchTool` | ⭐ | 简单问题，快速备选检索（纯向量） |
| `DeepResearchTool` | ⭐⭐⭐⭐ | 复杂问题，需多步推理和深入挖掘 |
| `DeeperResearchTool` | ⭐⭐⭐⭐⭐ | 最复杂问题，需分支推理、动态图谱和证据链 |
| `ChainOfExplorationTool` | ⭐⭐⭐ | 沿关系链探索，从起始实体逐步扩展 |
| `HypothesisGeneratorTool` | ⭐ | 开放性问题，多角度假设分析（辅助工具） |
| `AnswerValidationTool` | ⭐ | 验证答案质量，确保相关性和可用性（辅助工具） |

## 六、使用方法

```python
# 通过工具注册表获取搜索工具
from backend.search.tool_registry import get_tool_class, create_extra_tool

# 基础搜索工具
HybridTool = get_tool_class("hybrid_search")
hybrid_search = HybridTool()
result = hybrid_search.search("设备故障原因分析")

# 深度研究
DeepTool = get_tool_class("deep_research")
deep_search = DeepTool()
result = deep_search.search("压缩机连续三次故障的根本原因")

# 专用工具
hypothesis_tool = create_extra_tool("hypothesis_generator")
hypotheses = hypothesis_tool.generate("导致电机过热的原因有哪些？")

validator_tool = create_extra_tool("answer_validator")
validation = validator_tool.validate(query, answer)

# 直接使用基础搜索类
from backend.search.local_search import LocalSearch
from backend.search.global_search import GlobalSearch

local_search = LocalSearch(llm, embeddings)
result = local_search.search("轴承磨损检测方法")
```

## 七、数据流转

1. **输入层**: 用户查询 → 各搜索工具
2. **检索层**: 搜索工具 → 原始检索结果（Documents、Entities、Relationships、Communities）
3. **适配层**: `retrieval_adapter` → 统一的 `RetrievalResult` 格式
4. **输出层**: 标准化检索结果 → Agent 或下游组件

这种统一的数据流转保证不同搜索工具之间的互操作性，便于在多 Agent 系统中集成使用。
