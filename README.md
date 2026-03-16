# O-Mind

OpenClaw 本地记忆服务 - 私有化部署的长久会话和记忆解决方案

## 特性

- 🧠 **长久记忆** - 会话历史自动保存到本地数据库
- 🔒 **私有化部署** - 所有数据存储在本地服务器
- ⚡ **自动化钩子** - 无需手动操作，自动完成记忆存取
- 🐳 **Docker 部署** - 一键部署，支持 Docker Compose

## 架构

```
OpenClaw (Agent)
    ↓ skill + hook
O-Mind API Server (FastAPI)
    ↓
MySQL (结构化存储) + Qdrant (向量搜索)
```

## 快速开始

### 1. 启动服务

```bash
docker-compose up -d
```

### 2. 验证服务

```bash
# 检查健康状态
curl http://localhost:8000/health

# 查看所有记忆
curl http://localhost:8000/api/memories
```

### 3. 配置 OpenClaw

在 OpenClaw 配置文件中添加：

```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://localhost:8000"
  },
  "skills": {
    "paths": ["./skills"]
  }
}
```

## API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/memories | 创建记忆 |
| GET | /api/memories | 搜索记忆 |
| GET | /api/memories/{id} | 获取单条 |
| PUT | /api/memories/{id} | 更新记忆 |
| DELETE | /api/memories/{id} | 删除记忆 |

## Hook 自动化

- `before_prompt_build` - 每次对话前检索相关记忆
- `before_reset` - /reset 前保存会话摘要
- `agent_end` - 对话完成后保存内容

## 技术栈

- FastAPI + Uvicorn
- MySQL 8
- Qdrant (向量数据库)
- Docker Compose

## 项目结构

```
O-Mind/
├── api/                  # FastAPI 服务
├── skill-memory-server/ # OpenClaw Skill
├── hooks/              # Hook 自动化
├── docker-compose.yml   # 部署配置
├── Dockerfile          # 镜像构建
└── README.md
```

## License

MIT
