# Memory Server 自建服务

## 项目信息
- **项目名称**: memory-server
- **项目路径**: E:\paperclip_workspace\memory-server
- **描述**: 自建记忆服务，替代 mem9，提供持久化记忆 API

## 技术栈
- **API 框架**: FastAPI (Python)
- **向量数据库**: Qdrant (Docker 部署)
- **结构化存储**: MySQL (已有服务器)
- **Embedding 模型**: Ollama + bge-m3

## API 接口设计

### 记忆管理
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/memories | 创建记忆 |
| GET | /api/memories | 搜索记忆 (q=xxx) |
| GET | /api/memories/{id} | 获取单条记忆 |
| PUT | /api/memories/{id} | 更新记忆 |
| DELETE | /api/memories/{id} | 删除记忆 |

### 数据模型
```python
Memory:
  - id: str (UUID)
  - content: str
  - tags: list[str]
  - source: str (agent_id)
  - metadata: dict (可选)
  - created_at: datetime
  - updated_at: datetime
```

## 目录结构
```
memory-server/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPI 应用
│   ├── routes/
│   │   ├── __init__.py
│   │   └── memories.py  # 记忆 CRUD 路由
│   └── models.py        # Pydantic 模型
├── services/
│   ├── __init__.py
│   ├── vector_store.py  # Qdrant 向量存储
│   ├── mysql_store.py   # MySQL 持久化
│   └── embedding.py     # Embedding 服务
├── docker-compose.yml   # Qdrant + Ollama 部署
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量示例
└── README.md
```

## 环境变量
```
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=memory
MYSQL_PASSWORD=xxx
MYSQL_DATABASE=memory

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# 服务
API_SECRET=your-secret-key
```

## OpenClaw Skill 集成
创建 skill-memory-server/ 目录，包含:
- SKILL.md: 技能说明
- index.ts: 调用本地 memory-server API
