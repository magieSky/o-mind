# O-Mind

> OpenClaw 本地记忆服务 - 私有化部署的长久会话和记忆解决方案

## ✨ 特性

- 🧠 **长久记忆** - 会话历史自动保存到本地数据库
- 🔒 **私有化部署** - 所有数据存储在本地服务器，安全可控
- ⚡ **自动化钩子** - 无需手动操作，自动完成记忆存取
- 🔍 **向量搜索** - 支持语义相似度搜索
- 🐳 **Docker 部署** - 一键部署，支持 Docker Compose

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenClaw Agent                          │
│              (记忆测试员 / memory-tester)                    │
└─────────────────────────┬───────────────────────────────────┘
                        │ REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    O-Mind API Server                         │
│                  (FastAPI + Uvicorn)                        │
├─────────────────┬─────────────────┬───────────────────────┤
│   MySQL         │   Qdrant        │   Hooks             │
│  (结构化存储)    │  (向量数据库)    │  (自动化)           │
└─────────────────┴─────────────────┴───────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker
- Docker Compose

### 1. 克隆项目

```bash
git clone https://gitlab.bjhzsk.cn/develop/o-mind.git
cd o-mind
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 验证服务

```bash
# 检查健康状态
curl http://localhost:8000/health

# 查看所有记忆
curl http://localhost:8000/api/memories
```

### 4. 配置 OpenClaw

在 OpenClaw 容器中配置：

```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://o-mind-api:8000"
  },
  "skills": {
    "paths": ["/workspace/skills"]
  }
}
```

## 📡 API 接口

### 创建记忆

```bash
curl -X POST http://localhost:8000/api/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户喜欢蓝色",
    "tags": ["preference", "color"],
    "source": "test"
  }'
```

### 搜索记忆

```bash
# 关键词搜索
curl "http://localhost:8000/api/memories?q=喜欢"

# 向量搜索
curl "http://localhost:8000/api/memories/search/vector?query=用户偏好&limit=5"
```

### 获取单条记忆

```bash
curl http://localhost:8000/api/memories/{id}
```

### 更新记忆

```bash
curl -X PUT http://localhost:8000/api/memories/{id} \
  -H "Content-Type: application/json" \
  -d '{"content": "新内容"}'
```

### 删除记忆

```bash
curl -X DELETE http://localhost:8000/api/memories/{id}
```

## ⚓ Hook 自动化

O-Mind 通过 Hook 实现自动化记忆管理：

| Hook | 触发时机 | 行为 |
|------|----------|------|
| `before_prompt_build` | 每次 LLM 调用前 | 自动检索相关记忆并注入上下文 |
| `before_reset` | 执行 /reset 前 | 自动保存会话摘要 |
| `agent_end` | Agent 完成后 | 自动保存对话内容 |

### 配置 Hook

在 OpenClaw 配置中添加：

```json
{
  "hooks": {
    "memory-server-hook": {
      "enabled": true
    }
  }
}
```

## 🐳 部署

### 开发环境

```bash
docker-compose up -d
```

### 生产环境

```bash
# 使用外部数据库
docker-compose -f docker-compose.prod.yml up -d
```

### 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| O-Mind API | 8000 | REST API |
| MySQL | 3306 | 数据库 |
| Qdrant | 6333 | 向量数据库 |

## 🛠️ 项目结构

```
O-Mind/
├── api/                      # FastAPI 服务
│   ├── __init__.py
│   └── main.py              # 主服务代码
├── skill-memory-server/       # OpenClaw Skill
│   ├── SKILL.md
│   └── index.ts
├── hooks/                    # Hook 自动化
│   └── memory-server-hook/
│       ├── HOOK.md
│       └── handler.js
├── docker-compose.yml        # Docker Compose 配置
├── Dockerfile               # API 服务镜像
├── requirements.txt         # Python 依赖
└── README.md               # 项目说明
```

## 🔧 故障排除

### 服务无法启动

```bash
# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

### 无法连接数据库

```bash
# 检查数据库状态
docker-compose ps

# 重建数据库
docker-compose down -v
docker-compose up -d
```

### 记忆未保存

```bash
# 检查 API 服务日志
docker logs o-mind-api

# 验证数据库连接
curl http://localhost:8000/health
```

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
