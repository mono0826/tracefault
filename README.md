# 企业设备故障问答系统

基于 LangChain + LangGraph + Streamlit 的企业级设备故障智能问答平台。

## 技术栈

- **前端**: Streamlit（`frontend/`）
- **后端**: LangChain / LangGraph / SQLAlchemy（`backend/`）
- **数据库**: MySQL / SQLite (SQLAlchemy ORM)
- **向量存储**: Chroma / FAISS
- **LLM**: 兼容 OpenAI / 国产大模型 API

## 项目结构

```
equipment-fault-qa/
├── backend/                # 后端业务逻辑
│   ├── config.py           # 配置管理
│   ├── agent/              # LangGraph 智能体
│   ├── knowledge/          # 知识库（加载、向量化、检索）
│   ├── database/           # 数据库模型与连接
│   ├── pipelines/          # 文件处理流水线
│   └── utils/              # 后端工具函数
├── frontend/               # Streamlit 前端
│   ├── main.py             # 应用入口
│   ├── pages/              # 多页面（知识管理、管理后台）
│   ├── components/         # 可复用 UI 组件
│   └── utils/              # 前端工具函数
├── data/                   # 数据目录
│   ├── documents/          # 上传的文档
│   └── vector_store/       # 向量索引
├── scripts/                # 运维脚本
├── tests/                  # 测试
└── requirements.txt        # 依赖清单
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填写数据库和 LLM 配置

# 初始化数据库
python scripts/init_db.py

# 启动前端
streamlit run frontend/main.py
```

## 功能模块

- **💬 智能问答**: 基于 RAG 的设备故障诊断对话
- **📚 知识管理**: 设备手册、故障案例的增删改查
- **🔧 工单联动**: 故障上报 → 诊断 → 维修闭环（规划中）
- **📊 数据看板**: 故障统计分析（规划中）
