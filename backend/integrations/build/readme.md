# integrations/build 模块 — 知识图谱构建与增量更新

提供完整的知识图谱构建链路：**基础图谱构建 → 实体索引 + 社区检测 → Chunk 向量索引**，以及高效**增量更新**机制，避免全量重建。

---

## 目录结构

```
integrations/build/
├── __init__.py                           # 模块入口（空）
├── readme.md                             # 本文件
├── main.py                               # 完整构建流程编排器 — KnowledgeGraphProcessor
├── build_graph.py                        # 基础图谱构建器 — KnowledgeGraphBuilder
├── build_index_and_community.py          # 实体索引 + 社区检测 — IndexCommunityBuilder
├── build_chunk_index.py                  # Chunk 向量索引 — ChunkIndexBuilder
├── incremental_graph_builder.py          # 增量图谱更新器 — IncrementalGraphUpdater
├── incremental_update.py                 # 增量更新管理器 + CLI — IncrementalUpdateManager
└── incremental/
    ├── __init__.py                       # 增量更新子模块入口（空）
    ├── file_change_manager.py            # 文件变更追踪器 — FileChangeManager
    ├── incremental_update_scheduler.py   # 定时调度器 — IncrementalUpdateScheduler
    └── manual_edit_manager.py            # 手动编辑保护 — ManualEditManager
```

---

## 数据流

### 全量构建流程

```
KnowledgeGraphProcessor.process_all()
        │
        ├─ 步骤 0: 清除旧索引
        │      connection_manager.drop_all_indexes()
        │
        ├─ 步骤 1: 基础图谱构建 ──────────────────────────────────┐
        │   KnowledgeGraphBuilder.process()                       │
        │   文件读取 → 中文分块 → LLM 抽取实体/关系 → 写入 Neo4j   │
        │                                                         │
        ├─ 步骤 2: 实体索引 + 社区 ────────────────────────────────┤
        │   IndexCommunityBuilder.process()                       │
        │   实体向量索引 → 消歧/对齐 → 相似实体合并 → 社区检测     │
        │                                                         │
        └─ 步骤 3: Chunk 向量索引 ────────────────────────────────┘
            ChunkIndexBuilder.process()
            Chunk Embedding → 向量索引（支持 Naive RAG）
```

### 增量更新流程

```
IncrementalUpdateManager.run_once()
        │
        ├─ 1. detect_file_changes()
        │      FileChangeManager: 哈希比对 → 增/改/删列表
        │
        ├─ 2. 处理新增文件
        │      IncrementalGraphUpdater.process_new_files()
        │      临时目录 → 分块 → 抽取 → 写入（复用全量流程）
        │
        ├─ 3. 处理删除文件
        │      IncrementalGraphUpdater.process_deleted_files()
        │      级联删除文档/Chunk/孤立实体节点
        │
        ├─ 4. 更新 Embedding
        │      EmbeddingManager: 标记需更新实体 → 向量重计算
        │
        ├─ 5. 图谱一致性验证
        │      GraphConsistencyValidator: 孤立节点/断链/完整性
        │
        ├─ 6. 手动编辑保护
        │      ManualEditManager: 检测 → 标记 → 防覆盖
        │
        └─ 7. 社区检测（可选）
              CommunityDetectorFactory + CommunitySummarizerFactory
```

---

## 核心构建器详解

### 1. KnowledgeGraphProcessor（main.py）

全量构建流程的顶层编排器，按顺序串联三个构建阶段。

```python
from backend.integrations.build.main import KnowledgeGraphProcessor

processor = KnowledgeGraphProcessor()
processor.process_all()
# → 控制台分步输出，异常时终止并打印错误
```

**执行顺序：**
1. 清除所有旧索引（防止索引冲突）
2. `KnowledgeGraphBuilder` 构建基础图谱
3. `IndexCommunityBuilder` 构建实体索引 + 社区
4. `ChunkIndexBuilder` 构建 Chunk 向量索引

---

### 2. KnowledgeGraphBuilder（build_graph.py）

基础知识图谱构建器，负责从原始文档生成图结构。

```python
from backend.integrations.build.build_graph import KnowledgeGraphBuilder

builder = KnowledgeGraphBuilder()
processed_documents = builder.process()
```

**内部流程：**

| 步骤 | 组件 | 产出 |
|---|---|---|
| 1. 文档读取 | `DocumentProcessor` | `List[Document]` |
| 2. 中文分块 | `ChineseTextChunker` | 每个 Document → `List[Chunk]` |
| 3. 图结构创建 | `GraphStructureBuilder` | Document → Chunk 层级关系 |
| 4. 实体/关系抽取 | `EntityRelationExtractor` | LLM 从 Chunk 抽取 `(entity)` / `(relationship)` |
| 5. 图写入 | `GraphWriter` | 写入 Neo4j: 实体节点 + 关系 + Chunk→实体关联 |

**资源自适应：**
- 并行度 = min(CPU 核心数 - 1, MAX_WORKERS)
- 批次大小根据系统内存动态估算
- 超长文本自动降级为段落级处理

---

### 3. IndexCommunityBuilder（build_index_and_community.py）

在基础图谱之上构建实体索引、提升实体质量、检测社区。

```python
from backend.integrations.build.build_index_and_community import IndexCommunityBuilder

index_builder = IndexCommunityBuilder()
index_builder.process()
```

**子流程：**

| 阶段 | 组件 | 说明 |
|---|---|---|
| 实体向量索引 | `EntityIndexManager` | 为实体创建 Embedding + 向量索引 |
| 实体消歧 | `EntityDisambiguator` | 编辑距离召回 → 向量重排 → NIL 检测 → 设 canonical_id |
| 实体对齐 | `EntityAligner` | 按 canonical_id 分组 → 冲突检测 → LLM 裁决 → 合并 |
| 相似实体检测 | `SimilarEntityDetector` (GDS) | 基于图算法的相似度计算 |
| 实体合并 | `EntityMerger` | 合并相似实体，保留关系和属性 |
| 社区检测 | `CommunityDetectorFactory` | Leiden / SLLPA 算法 |
| 社区摘要 | `CommunitySummarizerFactory` | LLM 生成社区摘要 |

**实体质量提升机制：**
```
原始实体
    │
    ├─ 消歧: "张三" vs "张 三" → canonical_id 指向同一实体
    │
    ├─ 冲突检测: 同一 canonical_id 下 "张三(年龄35)" vs "张三(年龄40)"
    │   → LLM 裁决保留哪个
    │
    └─ 合并: 指向同一 canoncial 的实体合并，关系去重保留
```

---

### 4. ChunkIndexBuilder（build_chunk_index.py）

为 Chunk 节点创建向量索引，支撑 Naive RAG 检索。

```python
from backend.integrations.build.build_chunk_index import ChunkIndexBuilder

chunk_builder = ChunkIndexBuilder()
chunk_builder.process()
```

- 查找所有需要 Embedding 的 Chunk
- 调用 `ChunkIndexManager` 批量生成向量
- 创建向量索引（用于语义相似性检索）

---

## 增量更新

### IncrementalGraphUpdater（incremental_graph_builder.py）

增量图谱更新的执行单元，只处理变更部分。

```python
from backend.integrations.build.incremental_graph_builder import IncrementalGraphUpdater

updater = IncrementalGraphUpdater(files_dir="./data")
updater.process_incremental_update()
```

**变更处理策略：**

| 变更类型 | 处理方式 |
|---|---|
| **新增文件** | 全流程：临时目录 → 分块 → 抽取 → 写入（隔离处理，不影响现有图结构） |
| **修改文件** | 重新抽取实体/关系 + 更新 Embedding |
| **删除文件** | 级联删除：文档节点 → Chunk 节点 → 孤立实体节点（保护手动编辑的实体） |

**增量合并算法：**
- 节点：按 ID 合并，新时间戳覆盖旧属性，标记 `needs_reembedding`
- 关系：`(source, type, target)` 三元组去重，时间戳较新者保留
- 孤立实体保护：`manual_edit = true` 或 `protected = true` 的实体不被级联删除

---

### IncrementalUpdateManager（incremental_update.py）

增量更新管理的顶层封装，支持调度和 CLI。

```python
from backend.integrations.build.incremental_update import IncrementalUpdateManager

# 单次执行
manager = IncrementalUpdateManager(files_dir="./data")
manager.run_once()

# 后台调度
manager.start_scheduler()
```

**子组件调度：**

| 组件 | 方法 | 默认频率 |
|---|---|---|
| 文件变更检测 | `detect_file_changes()` | 5 分钟 |
| 实体 Embedding 更新 | `update_entity_embeddings()` | 10 分钟 |
| Chunk Embedding 更新 | `update_chunk_embeddings()` | 10 分钟 |
| 图谱一致性验证 | `verify_graph_consistency()` | 30 分钟 |
| 社区检测 | `detect_communities()` | 30 分钟 |
| 手动编辑检查 | `check_manual_edits()` | 15 分钟 |

---

## 增量更新子组件

### FileChangeManager（incremental/file_change_manager.py）

追踪文件变更，基于文件哈希 + JSON 注册表。

```python
from backend.integrations.build.incremental.file_change_manager import FileChangeManager

manager = FileChangeManager(files_dir="./data")
changes = manager.detect_changes()
# → {"added": [...], "modified": [...], "deleted": [...]}

manager.update_registry()
manager.clear_registry()     # 清空注册表（强制全量重建）
manager.print_registry()     # 调试用
```

**注册表结构：** JSON 文件，记录每个文件的路径、哈希值、最后修改时间。

---

### IncrementalUpdateScheduler（incremental/incremental_update_scheduler.py）

基于 `schedule` 库的轻量级定时调度器。

```python
from backend.integrations.build.incremental.incremental_update_scheduler import IncrementalUpdateScheduler

scheduler = IncrementalUpdateScheduler(config={...})

# 注册组件
scheduler.schedule_component("file_change", my_handler)
scheduler.schedule_component("entity_embedding", my_handler)

# 启动/停止
stop_event = scheduler.start()
scheduler.stop(stop_event)
scheduler.print_status()
```

**频率配置：** 每个组件可独立配置 `threshold`（秒），到时间自动执行。

---

### ManualEditManager（incremental/manual_edit_manager.py）

保护用户手动编辑的实体/关系不被增量更新覆盖。

```python
from backend.integrations.build.incremental.manual_edit_manager import ManualEditManager

edit_manager = ManualEditManager()

# 检测手动编辑
stats = edit_manager.detect_manual_edits()
# → {"manual_entities": N, "manual_relations": M}

# 应用保护标记
result = edit_manager.preserve_manual_edits(changed_files)

# 同步变更并保护手动编辑
result = edit_manager.process(changed_files)
```

**保护机制：**
1. 检测：扫描数据库中 `manual_edit = true` 标签
2. 标记：对受保护的节点设置 `protected = true`
3. 冲突解决：可配置策略（`manual_override` / `auto_merge` / `prompt`）
4. 增量更新中所有删除操作跳过受保护的节点

---

## 命令行用法

### 全量构建
```bash
python backend/integrations/build/main.py
```

### 增量更新（单次）
```bash
python backend/integrations/build/incremental_update.py --once
```

### 增量更新（守护进程）
```bash
python backend/integrations/build/incremental_update.py --daemon --interval 300
```

**CLI 参数：**

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--dir` | `FILES_DIR` | 监控的文件目录 |
| `--once` | — | 执行一次更新后退出 |
| `--daemon` | — | 守护进程模式 |
| `--interval` | 300 | 文件检测间隔（秒） |
| `--community-interval` | 1800 | 社区检测间隔（秒） |
| `--manual-check-interval` | 900 | 手动编辑检查间隔（秒） |

**交互模式命令：**
```
>>> run      执行一次完整增量更新
>>> stats    显示统计信息
>>> exit     退出程序
>>> help     显示帮助
```

---

## 资源自适应策略

所有构建器根据运行时环境动态调整参数：

| 资源 | 检测方式 | 自适应行为 |
|---|---|---|
| CPU 核心 | `os.cpu_count()` | 并行度 = min(cpu - 1, MAX_WORKERS) |
| 可用内存 | `psutil.virtual_memory()` | 批次大小 = min(自动估算, MEMORY_LIMIT) |
| 文件体积 | 文件大小检测 | >500KB 超长文本自动段落预分割 |

---

## 扩展：添加新的构建阶段

1. 在 `integrations/build/` 下新建 `build_xxx.py`
2. 定义构建器类，实现 `process()` 方法
3. 在 `main.py` 的 `KnowledgeGraphProcessor.process_all()` 中添加调用
4. 在 `incremental_update.py` 的 `run_once()` 中添加增量更新步骤
