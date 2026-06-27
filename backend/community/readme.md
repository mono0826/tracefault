# 社区检测与摘要模块

## 目录结构

```
backend/community/
├── __init__.py                    # 模块入口，导出工厂类
├── readme.md                      # 本文档
├── detector/                      # 社区检测器
│   ├── __init__.py                # 检测器工厂类
│   ├── base.py                    # 基础检测器抽象类
│   ├── leiden.py                  # Leiden 算法实现
│   ├── sllpa.py                   # SLLPA 算法实现
│   └── projections.py             # 图投影混入类
└── summary/                       # 社区摘要生成器
    ├── __init__.py                # 摘要工厂类
    ├── base.py                    # 基础摘要生成器抽象类
    ├── leiden.py                  # Leiden 社区摘要实现
    └── sllpa.py                   # SLLPA 社区摘要实现
```

---

## 节点与关系类型

### 核心节点

| 标签 | 说明 | 关键属性 |
|------|------|---------|
| `__Entity__` | 实体节点（已由图谱构建模块创建） | `id`, `type`, `description`, `embedding`, `communities`(Leiden), `communityIds`(SLLPA) |
| `__Community__` | 社区节点（本模块创建） | `id`, `level`, `summary`, `community_rank`, `summary_created_at`, `algorithm` |
| `__Chunk__` | 文本块节点（摘要排名用） | `id`, `text` |

### 定义的关系

| 关系类型 | 起点→终点 | 含义 |
|----------|----------|------|
| `IN_COMMUNITY` | `__Entity__`→`__Community__` | 实体所属社区 |
| `IN_COMMUNITY` | `__Community__`→`__Community__` | 社区层级隶属关系（Leiden 多层级） |
| `MENTIONS` | `__Chunk__`→`__Entity__` | 块中提及的实体（用于计算社区排名） |

---

## 完整流水线

```
                    ┌──────────────────────────────┐
                    │   图谱构建完成后的实体图       │
                    │   __Entity__ 节点 + 关系       │
                    └──────────────┬───────────────┘
                                   │
                     ┌─────────────▼──────────────┐
                     │  Phase 1: 社区检测         │
                     │  detector/                 │
                     │                            │
                     │  1. create_projection()    │
                     │     → GDS 内存图投影        │
                     │     → 三级降级策略           │
                     │                            │
                     │  2. detect_communities()   │
                     │     → Leiden / SLLPA 算法   │
                     │     → WCC 连通分量分析      │
                     │                            │
                     │  3. save_communities()     │
                     │     → __Community__ 节点    │
                     │     → IN_COMMUNITY 关系     │
                     │                            │
                     │  4. cleanup()              │
                     │     → 释放 GDS 投影内存     │
                     └─────────────┬──────────────┘
                                   │
                     ┌─────────────▼──────────────┐
                     │  Phase 2: 社区摘要         │
                     │  summary/                  │
                     │                            │
                     │  1. calculate_ranks()      │
                     │     → 按关联 Chunk 数排名   │
                     │                            │
                     │  2. collect_community_     │
                     │     info()                 │
                     │     → 收集实体+关系         │
                     │     → 分批处理(大数据量)    │
                     │                            │
                     │  3. LLM 生成摘要           │
                     │     → ThreadPoolExecutor   │
                     │     → 并行调用 LLM          │
                     │                            │
                     │  4. store_summaries()      │
                     │     → __Community__.summary │
                     └───────────────────────────┘
```

---

## 各阶段详解

### Phase 1: 社区检测（detector/）

#### 1a. 图投影（GraphProjectionMixin）

**文件**: `detector/projections.py`

将 Neo4j 原生图投影到 GDS 内存图，供算法执行。包含**三级降级策略**应对不同规模数据：

```
create_projection()
  │
  ├─ _get_node_count()
  │     MATCH (e:__Entity__) RETURN count(e)
  │
  ├─ 节点数 ≤ node_count_limit
  │     → 标准投影：投影所有 __Entity__ 节点 + 全部关系（UNDIRECTED）
  │
  ├─ 节点数 > node_count_limit
  │     → 过滤投影：按度数排序取 topN 节点 + 其关系
  │
  ├─ 过滤投影失败
  │     → 保守投影：最小配置（无属性）
  │
  └─ 保守投影失败
        → 最小化投影：仅分析 1000 个关键节点
```

**参数自适应**（`_adjust_parameters`）：

| 可用内存 | node_count_limit | timeout_seconds | 适用场景 |
|----------|-----------------|-----------------|---------|
| > 32GB | 100,000 | 600 | 大规模生产环境 |
| > 16GB | 50,000 | 300 | 中等规模 |
| ≤ 16GB | 20,000 | 180 | 开发/小规模测试 |

`node_count_limit` 控制何时进入过滤模式，而非硬性容量上限。

---

#### 1b. BaseCommunityDetector

**文件**: `detector/base.py`

**抽象基类**，定义社区检测的标准流程骨架：

```
process()
  │
  ├─ _graph_projection_context()  [上下文管理器]
  │     ├─ create_projection()
  │     └─ yield
  │
  ├─ detect_communities()  [抽象方法]
  │     → 子类实现具体算法
  │
  ├─ save_communities()  [抽象方法]
  │     → 子类实现持久化逻辑
  │
  └─ cleanup()  [自动执行]
        → G.drop() 释放投影内存
```

**资源管理**：
- 使用 `@contextmanager` 确保投影资源在 `finally` 中释放
- 收集 `projection_time` / `detection_time` / `save_time` 性能统计
- **错误处理**：任何阶段失败记录 `{'status': 'error', 'error': str(e)}` 后 `raise`，由上层捕获

---

#### 1c. LeidenDetector

**文件**: `detector/leiden.py`

基于模块度优化的分层聚类算法，适用于大规模图，**默认选择**。

**关键流程**：

```
detect_communities()
  │
  ├─ wcc.stats()
  │     → 输出连通分量数量和分布
  │
  ├─ gds.leiden.write()
  │     writeProperty="communities"
  │     includeIntermediateCommunities=true  → 支持多层级社区
  │     relationshipWeightProperty="weight"
  │     params → _get_optimized_leiden_params()
  │
  └─ 失败 → _execute_fallback_leiden()
        gamma=0.5, tolerance=0.001, maxLevels=2, concurrency=1
```

**参数优化**（`_get_optimized_leiden_params`）：

| 内存 | gamma | tolerance | maxLevels | concurrency |
|------|-------|-----------|-----------|-------------|
| > 32GB | 1.0 | 0.0001 | 10 | `GDS_CONCURRENCY` |
| > 16GB | 1.0 | 0.0005 | 5 | `max(1, GDS_CONCURRENCY - 1)` |
| ≤ 16GB | 0.8 | 0.001 | 3 | `max(1, GDS_CONCURRENCY // 2)` |

**社区保存**（`save_communities`）：

```
save_communities()
  │
  ├─ CREATE CONSTRAINT IF NOT EXISTS FOR (c:__Community__) REQUIRE c.id IS UNIQUE
  │
  ├─ 保存基础层（level 0）社区
  │     MATCH (e) WHERE e.communities[0] IS NOT NULL
  │     → MERGE (c:__Community__ {id: '0-' + community_id})
  │     → MERGE (e)-[:IN_COMMUNITY]->(c)
  │
  └─ 保存高层级社区关系（communities[1..N]）
        → MERGE (c_prev)-[:IN_COMMUNITY]->(c_current)
```

---

#### 1d. SLLPADetector

**文件**: `detector/sllpa.py`

Speaker-Listener Label Propagation Algorithm，基于标签传播，适合检测**重叠社区**。

**关键流程**：

```
detect_communities()
  │
  ├─ gds.sllpa.write()
  │     writeProperty="communityIds"
  │     params → _get_optimized_sllpa_params()
  │
  └─ 失败 → _execute_fallback_sllpa()
        maxIterations=50, minAssociationStrength=0.2, concurrency=1
```

**参数优化**（`_get_optimized_sllpa_params`）：

| 内存 | maxIterations | minAssociationStrength | concurrency |
|------|---------------|----------------------|-------------|
| > 32GB | 100 | 0.05 | `GDS_CONCURRENCY` |
| > 16GB | 80 | 0.08 | `max(1, GDS_CONCURRENCY - 1)` |
| ≤ 16GB | 50 | 0.1 | `max(1, GDS_CONCURRENCY // 2)` |

**自动回退**：如果 SLLPA 未检测到社区，会自动切换到 Leiden 算法，保证始终输出可用的社区划分。

---

### Phase 2: 社区摘要（summary/）

#### 2a. BaseSummarizer

**文件**: `summary/base.py`

**抽象基类**，定义社区摘要生成的标准流程骨架：

```
process_communities()
  │
  ├─ 1. ranker.calculate_ranks()
  │     按社区关联的 Chunk 数排序（社区重要性排名）
  │     主方案：MATCH (Chunk)-[:MENTIONS]->(Entity)-[:IN_COMMUNITY]->(Community)
  │               SET c.community_rank = count(distinct Chunk)
  │     回退方案：按 Entity 数量作为排名
  │
  ├─ 2. collect_community_info()  [抽象方法]
  │     子类实现具体查询逻辑
  │     → 返回 [{communityId, nodes[], rels[]}]
  │
  ├─ 3. _process_communities_parallel()
  │     ThreadPoolExecutor 并行调用 LLM
  │     每个线程: prepare_string() → LLM.invoke() → 摘要文本
  │     进度输出: 每 10 个打印一次
  │
  └─ 4. storer.store_summaries()
        → UNWIND $data MERGE (c:__Community__ {id}) SET c.summary = ...
        → 批处理失败 → 逐个存储（回退）
```

**LLM 链设置**：
```
ChatPromptTemplate:
  system: COMMUNITY_SUMMARY_PROMPT
  human: "{community_info}"

→ community_chain = prompt | llm | StrOutputParser()
```

**并行控制**：
- `optimal_workers = min(MAX_WORKERS, max(1, len(community_info) // 2))`
- 每 10 个摘要打印进度百分比

**性能统计**（`_print_performance_stats`）：

| 阶段 | 耗时占比 |
|------|---------|
| 社区权重计算 | `rank_time / total_time * 100%` |
| 社区信息查询 | `query_time / total_time * 100%` |
| 摘要生成(LLM) | `llm_time / total_time * 100%` |
| 结果存储 | `store_time / total_time * 100%` |

---

#### 2b. BaseCommunityDescriber

**文件**: `summary/base.py`

社区信息格式化工具：

```
prepare_string(data)
  │
  ├─ 遍历 nodes
  │     → "id: {id}, type: {type}, description: {description}"
  │
  └─ 遍历 rels
        → "({start})-[:{type}]->({end}), description: {description}"
```

---

#### 2c. BaseCommunityRanker

**文件**: `summary/base.py`

社区重要性计算：

| 方案 | 查询 | 说明 |
|------|------|------|
| 主方案 | `(Community)<-[:IN_COMMUNITY*]-(Entity)<-[:MENTIONS]-(Chunk)` | 按关联 Chunk 数排名 |
| 回退方案 | `(Community)<-[:IN_COMMUNITY]-(Entity)` | 按实体数排名 |

---

#### 2d. BaseCommunityStorer

**文件**: `summary/base.py`

摘要持久化：

```
store_summaries(summaries)
  │
  ├─ 按 `batch_size = min(100, max(10, len(summaries) // 5))` 分批
  │
  ├─ 主方案: UNWIND $data MERGE 并发处理
  │     → SET c.summary, c.full_content, c.summary_created_at
  │
  └─ 失败 → _store_summaries_one_by_one()
        → 逐条 MERGE
```

---

#### 2e. LeidenSummarizer

**文件**: `summary/leiden.py`

**信息收集**（`collect_community_info`）：

```
collect_community_info()
  │
  ├─ 1. COUNT 社区总数
  │
  ├─ 2. 社区数 ≤ 1000
  │     单次查询：按 rank 降序 LIMIT 200
  │     收集社区内实体 + 实体间关系
  │
  ├─ 3. 社区数 > 1000
  │     分批处理（batch_size=50），最多 20 批
  │
  └─ 4. 主查询失败 → _collect_info_fallback()
        简化查询：仅返回节点，不包含关系
```

**返回格式**：
```json
{
  "communityId": "0-42",
  "nodes": [{"id": "...", "description": "...", "type": "..."}],
  "rels": [{"start": "...", "type": "...", "end": "...", "description": "..."}]
}
```

---

#### 2f. SLLPASummarizer

**文件**: `summary/sllpa.py`

与 LeidenSummarizer 逻辑对称，查询条件使用 `c.level = 0`（SLLPA 所有社区在同一层级），部分关系查询使用批次内采样优化（`nodes[0..20]`）。

---

## 算法选择指南

| 特性 | Leiden | SLLPA |
|------|--------|-------|
| **算法类型** | 基于模块度优化的分层聚类 | 基于标签传播的社区检测 |
| **适用场景** | 大规模图、清晰的社区边界 | 重叠社区、动态图 |
| **时间复杂度** | O(n log n) | O(m + n) |
| **社区类型** | 非重叠社区（可多层级） | 可检测重叠社区 |
| **参数敏感度** | 中等（分辨率参数影响粒度） | 较高（迭代次数、阈值） |
| **稳定性** | 高（确定性结果） | 中等（需多次运行） |
| **推荐使用** | 默认选择，适合大多数场景 | 需要检测重叠社区时 |
| **层级关系** | 支持中间层（includeIntermediateCommunities） | 单层（level 0） |

**配置方式**：
```bash
# .env
GRAPH_COMMUNITY_ALGORITHM=leiden  # 或 sllpa
```

---

## 配置参数

### 社区检测

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `GDS_MEMORY_LIMIT` | GDS 内存限制（GB） | 6 |
| `GDS_CONCURRENCY` | GDS 算法并发度 | 4 |
| `GRAPH_COMMUNITY_ALGORITHM` | 检测算法 | `leiden` |

### 社区摘要

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `MAX_WORKERS` | LLM 摘要并行线程数 | 4 |
| `BATCH_SIZE` | 社区信息批量获取大小 | 100 |

---

## 性能优化策略

| 策略 | 应用场景 |
|------|----------|
| **三级图投影降级** | 标准→过滤→保守→最小化，适配不同内存/数据规模 |
| **参数自适应** | 按系统内存自动调整算法参数（并发度、精度、层数） |
| **并行 LLM 摘要** | `ThreadPoolExecutor` 多线程并行生成摘要 |
| **社区信息分批查询** | `SKIP $skip LIMIT $batch_size` 分批，避免大查询 OOM |
| **摘要分批存储** | `UNWIND $data` 批量写入，失败回退逐条写入 |
| **资源自动清理** | 上下文管理器确保 GDS 投影内存释放 |
| **缓存避免** | `CREATE CONSTRAINT IF NOT EXISTS` 避免重复约束创建 |
| **进度追踪** | 每 10 个摘要打印进度百分比，每批存储打印批次进度 |

## 回退策略汇总

| 阶段 | 主方案 | 回退方案 |
|------|--------|---------|
| 图投影创建 | 标准投影 | 过滤投影 → 保守投影 → 最小化投影 |
| Leiden 社区检测 | 优化参数 | 备用参数（低精度、低并发） |
| SLLPA 社区检测 | SLLPA 算法 | 自动回退到 Leiden 算法 |
| 社区信息收集 | 含关系的完整查询 | 不含关系的简化查询 |
| 社区排名 | 按 Chunk 计数 | 按 Entity 计数 |
| 摘要存储 | 批量 UNWIND | 逐条 MERGE |

## 数据流转示意

```
图数据库                                    本模块处理后
──────────                                ─────────────
__Entity__ (id, type, desc)               __Entity__ (id, type, desc, communities)
    │                                          │
    │                                          ├─ communities: [0-42, 1-12]
    │                                          └─ IN_COMMUNITY→
    │                                              ┌─────────────────────┐
    │                                              │ __Community__       │
    └── MENTIONS(Chunk) ────→ calculate_rank ──→  │   id: "0-42"        │
                                                    │   level: 0          │
                                                    │   community_rank: 15│
                                                    │   summary: "..."    │  ← LLM 生成
                                                    │   summary_created_at│
                                                    └─────────────────────┘
```
