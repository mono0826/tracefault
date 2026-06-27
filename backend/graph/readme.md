# 图谱构建模块

## 目录结构

```
backend/graph/
├── __init__.py                    # 模块入口，导出主要类和函数
├── readme.md                      # 本文档
├── core/                          # 核心功能组件
│   ├── __init__.py                # 导出核心组件
│   ├── graph_connection.py        # 图数据库连接管理
│   ├── base_indexer.py            # 基础索引器类
│   └── utils.py                   # 工具函数(定时器、哈希生成等)
├── structure/                     # 图结构构建组件
│   ├── __init__.py                # 导出结构组件
│   └── struct_builder.py          # 图结构构建器
├── extraction/                    # 实体关系提取组件
│   ├── __init__.py                # 导出提取组件
│   ├── entity_extractor.py        # 实体关系提取器
│   └── graph_writer.py            # 图数据写入器
├── indexing/                      # 索引管理组件
│   ├── __init__.py                # 导出索引组件
│   ├── chunk_indexer.py           # 文本块索引管理
│   ├── entity_indexer.py          # 实体索引管理
│   └── embedding_manager.py       # 嵌入向量增量管理
├── processing/                    # 实体处理组件
│   ├── __init__.py                # 导出处理组件
│   ├── similar_entity.py          # 相似实体检测（基于 GDS）
│   ├── entity_merger.py           # 实体合并（基于 LLM 决策）
│   ├── entity_disambiguation.py   # 实体消歧（string→vector→NIL）
│   ├── entity_alignment.py        # 实体对齐（conflict detection→merge）
│   └── entity_quality.py          # 实体质量处理器（编排消歧+对齐）
└── graph_consistency_validator.py # 图谱一致性验证和修复
```

## 节点与关系类型

### 核心节点

| 标签 | 说明 | 关键属性 |
|------|------|---------|
| `__Document__` | 文档节点 | `fileName`, `file_hash`, `type`, `uri`, `domain` |
| `__Chunk__` | 文本块节点 | `id`(SHA1), `text`, `position`, `fileName`, `content_offset`, `tokens`, `embedding` |
| `__Entity__` | 实体节点 | `id`, `type`, `description`, `embedding`, `wcc`, `canonical_id` |

### 定义的关系

| 关系类型 | 起点→终点 | 含义 |
|----------|----------|------|
| `PART_OF` | `__Chunk__`→`__Document__` | 文本块所属文档 |
| `NEXT_CHUNK` | `__Chunk__`→`__Chunk__` | 文本块顺序链 |
| `FIRST_CHUNK` | `__Document__`→`__Chunk__` | 文档的第一个块 |
| `MENTIONS` | `__Chunk__`→`__Entity__` | 块中提及的实体 |
| `SIMILAR` | `__Entity__`→`__Entity__` | KNN 检测出的相似实体（含 score） |

---

## 完整数据处理流水线

```
                   ┌──────────────────────────────┐
                   │     原始文档 / 文本 chunks     │
                   └──────────────┬───────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 1: 图结构构建       │
                    │  structure/struct_builder   │
                    │                             │
                    │  create_document()          │
                    │    → __Document__ 节点       │
                    │  create_relation_between_   │
                    │    chunks(chunks)           │
                    │    → __Chunk__ 节点         │
                    │    → PART_OF / NEXT_CHUNK / │
                    │      FIRST_CHUNK 关系       │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 2: 实体关系提取     │
                    │  extraction/               │
                    │                             │
                    │  EntityRelationExtractor    │
                    │    .process_chunks()        │
                    │    → LLM 提取实体+关系       │
                    │    → 本地 pickle 缓存       │
                    │                             │
                    │  GraphWriter                │
                    │    .process_and_write_      │
                    │     graph_documents()       │
                    │    → 正则解析 LLM 输出       │
                    │    → __Entity__ 节点         │
                    │    → 实体间关系              │
                    │    → MENTIONS(Chunk→Entity) │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 3: 向量索引建立     │
                    │  indexing/                 │
                    │                             │
                    │  ChunkIndexManager          │
                    │    .create_chunk_index()    │
                    │    → __Chunk__.embedding    │
                    │    → Chunk 向量索引         │
                    │                             │
                    │  EntityIndexManager         │
                    │    .create_entity_index()   │
                    │    → __Entity__.embedding   │
                    │    → Entity 向量索引        │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 4: 实体去重         │
                    │  processing/similar_entity │
                    │    + entity_merger.py      │
                    │                             │
                    │  SimilarEntityDetector      │
                    │    .process_entities()      │
                    │    → GDS 投影 → KNN        │
                    │    → SIMILAR 关系           │
                    │    → WCC 社区检测           │
                    │    → 候选重复组             │
                    │                             │
                    │  EntityMerger               │
                    │    .process_duplicates()    │
                    │    → LLM 判断合并           │
                    │    → apoc.refactor.merge-   │
                    │      Nodes执行合并          │
                    │    → 清理重复关系           │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 5: 实体质量提升     │
                    │  processing/               │
                    │                             │
                    │  EntityDisambiguator        │
                    │    .apply_to_graph()        │
                    │    → 字符串召回             │
                    │    → 向量重排               │
                    │    → NIL 检测               │
                    │    → 设置 canonical_id      │
                    │                             │
                    │  EntityAligner              │
                    │    .align_all()             │
                    │    → 按 canonical_id 分组   │
                    │    → Jaccard 冲突检测       │
                    │    → LLM 解决冲突           │
                    │    → 合并实体/转移关系      │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Stage 6: 一致性校验       │
                    │  graph_consistency_         │
                    │    validator.py             │
                    │                             │
                    │  .validate_graph()          │
                    │    → 孤立实体 / 悬空 Chunk  │
                    │    → 空 Chunk / 断链        │
                    │  .repair_graph()            │
                    │    → 删除/修复问题节点/关系 │
                    └───────────────────────────┘
```

---

## 各阶段详解

### Stage 0: 基础设施（core/）

**文件**: `core/graph_connection.py`, `core/base_indexer.py`, `core/utils.py`

| 组件 | 职责 |
|------|------|
| `GraphConnectionManager` | **单例**模式管理 Neo4j 连接；包装 `execute_query` / `create_index` / `drop_all_indexes` |
| `get_connection_manager()` | 懒加载全局连接管理器 |
| `BaseIndexer` | 索引器基类：封装批处理、进度跟踪、`ThreadPoolExecutor` 并行处理 |
| `timer` | 装饰器，打印函数执行耗时 |
| `generate_hash` | SHA1 哈希，用于生成 chunk_id |
| `batch_process` | 通用批处理工具，带进度百分比 |
| `retry` | 重试装饰器（最多 N 次，带延迟） |

`GraphConnectionManager` 通过 `backend.config.neo4jdb.get_db_manager()` 获取底层连接。

---

### Stage 1: 图结构构建（structure/struct_builder.py）

**输入**: `List[Chunk]`（`backend.pipelines.models.Chunk` 数据类）

```
Chunk(
    file_name: str,   # 来源文件名
    chunk_id: str,    # SHA1/空时自动生成
    doc_id: str,      # 文档 file_hash
    content: str      # 文本内容
)
```

**关键方法**:

| 方法 | 作用 |
|------|------|
| `clear_database()` | `MATCH (n) DETACH DELETE n` 清库 |
| `create_document(type, uri, file_name, domain)` | `MERGE` 创建 `__Document__` 节点 |
| `create_relation_between_chunks(chunks)` | 创建 `__Chunk__` 节点 + 结构关系 |
| `parallel_process_chunks(chunks)` | 大数据量时并行版本（超 100 个 chunk 自动启用） |

**核心逻辑** (`create_relation_between_chunks`)：

1. 遍历 chunks，为每个 chunk 生成 `chunk_id`（优先使用已有值，否则 SHA1）
2. 准备 batch 数据（含 id, text, position, fileName, content_offset, tokens）
3. 批量 `UNWIND $batch_data` 写入 Neo4j：
   - `MERGE (c:__Chunk__ {id}) SET ...`
   - `MATCH (d:__Document__ {fileName}) MERGE (c)-[:PART_OF]->(d)`
4. 建立 `FIRST_CHUNK`（Document→首个Chunk）和 `NEXT_CHUNK`（前→后）关系

**文件名约定**:

- Neo4j 标签使用双下划线包裹：`__Document__`、`__Chunk__`、`__Entity__`
- 属性使用 camelCase：`fileName`、`content_offset`

---

### Stage 2: 实体关系提取（extraction/）

#### 2a. EntityRelationExtractor

**文件**: `extraction/entity_extractor.py`

**流程**:

```
process_chunks(file_contents)
  │
  ├─ 对每个 chunk：检查 pickle 磁盘缓存（key=SHA1(content)）
  │
  ├─ 缓存命中 → 直接复用
  │
  ├─ 缓存未命中 → ThreadPoolExecutor 并行调 LLM
  │     LLM prompt: system_template + human_template
  │     → 提取实体: ("entity" : "id" : "type" : "desc")
  │     → 提取关系: ("relationship" : "src" : "tgt" : "type" : "desc" : weight)
  │
  └─ 结果写缓存 + 追加到 file_content 列表
```

**关键特性**:
- **本地缓存**: pickle 序列化，以 `SHA1(content)` 为键，位于 `./cache/graph/`
- **并行提取**: 使用 `ThreadPoolExecutor(max_workers)` 并行为每个 chunk 调 LLM
- **批处理模式**: `process_chunks_batch()` 将多个 chunk 合并为一个 LLM 请求（分隔符 `---`），减少调用次数
- **流式处理**: `stream_process_large_files()` 支持大文件的边读边处理模式
- **重试**: `@retry(times=3)` 装饰器确保单次调用失败后自动重试

#### 2b. GraphWriter

**文件**: `extraction/graph_writer.py`

将 LLM 输出的结构文本转换为 `GraphDocument` 并写入 Neo4j：

```
                                LLM 输出文本
                                     │
                                     ▼
convert_to_graph_document(chunk_id, text, result)
  │
  ├─ 正则解析实体: ("entity" : "id" : "type" : "desc")
  │     → Node(id, type, properties={'description': ...})
  │
  ├─ 正则解析关系: ("relationship" : "src" : "tgt" : "type" : "desc" : weight)
  │     → Relationship(source, target, type, properties)
  │
  ├─ Node 缓存: node_cache 减少重复 Node 创建
  │
  └─ → GraphDocument(nodes, relationships, source=Chunk Document)

process_and_write_graph_documents(file_contents)
  │
  ├─ ThreadPoolExecutor 并行转换所有 chunks
  │
  ├─ _batch_write_graph_documents()
  │     → graph.add_graph_documents(batch, baseEntityLabel=True, include_source=True)
  │
  └─ merge_chunk_relationships()
        → 将旧格式 Document 节点的 MENTIONS 迁移到 __Chunk__ 节点
```

---

### Stage 3: 向量索引建立（indexing/）

#### 3a. ChunkIndexManager

**文件**: `indexing/chunk_indexer.py`

继承 `BaseIndexer`，负责 `__Chunk__` 节点的 embedding 计算和向量索引。

```
create_chunk_index()
  │
  ├─ 清除已有索引 (chunk_embedding)
  │
  ├─ 查询 embedding IS NULL 的 chunk
  │
  ├─ batch_process_with_progress()
  │     ├─ _get_chunk_texts_batch()    → 批量读取 chunk text
  │     ├─ _compute_embeddings_batch() → embed_documents() 批量计算
  │     └─ _update_embeddings_batch()  → UNWIND $updates SET c.embedding
  │
  └─ Neo4jVector.from_existing_graph() → 创建向量检索接口
```

#### 3b. EntityIndexManager

**文件**: `indexing/entity_indexer.py`

逻辑与 ChunkIndexManager 对称：
- 使用 `id` + `description` 组合文本计算 embedding
- 创建 `__Entity__` 节点向量索引

#### 3c. EmbeddingManager（增量更新）

**文件**: `indexing/embedding_manager.py`

支持增量更新场景，不重建全量索引：

| 方法 | 功能 |
|------|------|
| `get_entities_needing_update()` | 查询 `embedding IS NULL` 或 `needs_reembedding = true` 的实体 |
| `get_chunks_needing_update()` | 同上 + 检测 `last_updated > last_embedded` 脏数据 |
| `update_entity_embeddings()` | 计算并更新实体 embedding |
| `update_chunk_embeddings()` | 计算并更新 chunk embedding |
| `mark_entities_for_update()` | 标记指定实体需重新 embedding |
| `mark_document_chunks_for_update()` | 标记文档下所有 chunk 需重新 embedding |
| `process()` | 完整流程：追踪设置 → 实体更新 → chunk 更新 → 统计 |

---

### Stage 4: 实体去重（processing/）

#### 4a. SimilarEntityDetector

**文件**: `processing/similar_entity.py`

基于 **Neo4j Graph Data Science (GDS)** 库的相似实体检测：

```
process_entities()
  │
  ├─ 1. create_entity_projection()
  │     将 __Entity__ 节点（含 embedding）投影到 GDS 内存图
  │     → gds.graph.project("entities", "__Entity__", "*", nodeProperties=["embedding"])
  │
  ├─ 2. detect_similar_entities()
  │     KNN 算法：基于 embedding 向量相似度
  │     → gds.knn.write(mutateRelationshipType='SIMILAR', similarityCutoff=threshold, topK=k)
  │     → 生成 SIMILAR 关系（含 score 属性）
  │
  ├─ 3. detect_communities()
  │     WCC 算法：连通分量检测
  │     → gds.wcc.write(writeProperty="wcc", relationshipTypes=["SIMILAR"])
  │     → 每个 Entity 节点写入 wcc 属性（社区 ID）
  │
  ├─ 4. find_potential_duplicates()
  │     查询同一 WCC 社区中编辑距离相近的实体对
  │     → 返回 [[e1, e2, ...], [e3, e4], ...] 候选组
  │
  └─ 5. cleanup()
        → 释放 GDS 内存投影图
```

**配置参数** (`GDSConfig`)：

| 参数 | 说明 |
|------|------|
| `similarity_threshold` | 向量相似度阈值 |
| `top_k` | KNN 返回的 topK |
| `word_edit_distance` | apoc.text.distance 编辑距离阈值 |
| `memory_limit` | GDS 内存限制 |

#### 4b. EntityMerger

**文件**: `processing/entity_merger.py`

基于 **LLM 决策**的实体合并：

```
process_duplicates(duplicate_candidates)
  │
  ├─ 过滤：去重、长度 > 1
  │
  ├─ get_merge_suggestions(candidates)
  │    对每组候选并行调 LLM：
  │      system_template_build_index + user_template_build_index
  │      → LLM 判断哪些实体应该合并
  │      → 返回 [[e1, e2], [e3, e4, e5], ...]
  │
  ├─ _convert_to_list(result)
  │    双重解析：ast.literal_eval 优先 → 正则回退
  │    合并有重叠的实体组（并查集）
  │
  ├─ execute_merges(merge_groups)
  │    分批执行 Neo4j 合并：
  │      CALL apoc.refactor.mergeNodes(nodes, {properties: {'.*': 'discard'}})
  │
  └─ clean_duplicate_relationships()
        → 删除同方向重复关系
        → 删除 SIMILAR 双向冗余（保留一个方向）
```

**回退策略**: 批处理失败时逐个处理，确保不因单个异常阻塞整批数据。

---

### Stage 5: 实体质量提升（processing/）

由 `EntityQualityProcessor` 编排，包含两个子阶段：

#### 5a. EntityDisambiguator

**文件**: `processing/entity_disambiguation.py`

**三级管道**：字符串召回 → 向量重排 → NIL 检测 → 写 `canonical_id`

```
              mention
                 │
                 ▼
    ┌────────────────────────┐
    │ 1. 字符串召回           │
    │ apoc.text.levenshtein- │
    │ Similarity(mention, id)│
    │ ≥ DISAMBIG_STRING_     │
    │ THRESHOLD              │
    └───────────┬────────────┘
                │
                ▼
    ┌────────────────────────┐
    │ 2. 向量重排             │
    │ cosine_similarity(     │
    │   mention_embed,       │
    │   entity_embed)        │
    │ combined_score =       │
    │   0.4*string + 0.6*vec │
    └───────────┬────────────┘
                │
                ▼
    ┌────────────────────────┐
    │ 3. NIL 检测             │
    │ combined_score <       │
    │ DISAMBIG_NIL_THRESHOLD │
    │ → 新实体（无 canonical） │
    └───────────┬────────────┘
                │
                ▼
    ┌────────────────────────┐
    │ 4. apply_to_graph()    │
    │ 分批处理 WCC 分组：     │
    │ 选 degree 最高的实体    │
    │ 为 canonical            │
    │ SET e.canonical_id =   │
    │   $canonical_id        │
    └────────────────────────┘
```

**分批策略**: 每轮查前 `batch_size` 个 `canonical_id IS NULL` 的分组，处理后自动从结果集消失，循环至无剩余。无需 SKIP 分页。

#### 5b. EntityAligner

**文件**: `processing/entity_alignment.py`

将相同 `canonical_id` 的实体对齐合并：

```
align_all()
  │
  ├─ 1. group_by_canonical_id()
  │     查询 MATCH (e) WHERE e.canonical_id IS NOT NULL
  │     → {canonical_id: [entity_ids]}
  │
  ├─ 2. detect_conflicts()
  │    比较组内实体的关系类型列表
  │    Jaccard 相似度 < ALIGNMENT_CONFLICT_THRESHOLD → 冲突
  │
  ├─ 3. resolve_conflict() [仅冲突组]
  │    LLM 判断保留哪个实体
  │    回退：保留关系数最多的
  │
  └─ 4. merge_entities()
        → CALL 子查询隔离边处理
        → 转移出边/入边到 target（去重）
        → 合并属性（保留非空值）
        → 记录 aligned_from / aligned_at
        → DETACH DELETE 旧实体
```

**关键特性**:
- 使用 `CALL { ... }` 子查询确保无边的分组也能正常走 SET/DELETE 流程
- 关系转移时检查类型+属性是否重复，避免产生重复边

---

### Stage 6: 图谱一致性校验

**文件**: `graph_consistency_validator.py`

| 检查项 | 查询逻辑 | 修复策略 |
|--------|----------|---------|
| 孤立实体 | NOT (e)<-[:MENTIONS]-() | 删除（排除 manual_edit/protected） |
| 悬空 Chunk | NOT (c)-[:PART_OF]->() | 删除 |
| 空 Chunk | c.text IS NULL OR '' | SET text='[Empty Chunk]' |
| 文档链接断裂 | NOT (d)-[:FIRST_CHUNK]->() | 重建 FIRST_CHUNK（找 position=1 的 chunk） |
| Chunk 链断裂 | position>1 且 NOT (c)<-[:NEXT_CHUNK]-() | 按 position 排序重建 NEXT_CHUNK |

也提供 `display_graph_stats()` 方法输出图谱节点和关系统计表（使用 Rich 库）。

---

## 性能优化策略

| 策略 | 应用场景 |
|------|----------|
| **批处理** | 所有写操作均使用 `UNWIND $batch_data` 批量提交 |
| **并行计算** | LLM 提取、embedding 计算、GraphDocument 转换均使用 `ThreadPoolExecutor` |
| **缓存机制** | EntityRelationExtractor 的 pickle 磁盘缓存（SHA1 key）避免重复 LLM 调用 |
| **回退策略** | 批处理失败→单个处理；主方案失败→备用参数/简化方案 |
| **索引优化** | 全流程多处 `CREATE INDEX IF NOT EXISTS` |
| **增量更新** | EmbeddingManager 支持脏数据检测和部分更新 |

## 分页策略对比

| 模块 | 策略 |
|------|------|
| EntityDisambiguator.apply_to_graph() | 每轮查前 N 个未处理的，处理后自动缩小结果集，无需 SKIP |
| EntityAligner.align_all() | 显式 `SKIP $skip` / `LIMIT $limit` 循环 |
| SimilarEntityDetector.find_potential_duplicates() | 无分页，单次查询（内存中做社区合并） |
