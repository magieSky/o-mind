# O-Mind

> OpenClaw 本地记忆服务 - 私有化部署的长久会话和记忆解决方案

## ✨ 特性

- 🧠 **长久记忆** - 会话历史自动保存到本地数据库
- 🔒 **私有化部署** - 所有数据存储在本地服务器，安全可控
- ⚡ **自动化钩子** - 无需手动操作，自动完成记忆存取
- 🔍 **向量搜索** - 支持语义相似度搜索（使用 bge-base-zh-v1.5）
- 📝 **会话摘要** - 每小时自动生成会话摘要，注入上下文
- 🐳 **Docker 部署** - 一键部署，支持 Docker Compose
- 🌐 **管理界面** - 可视化管理记忆和 Agent
- 🔑 **多实例隔离** - 支持多个 OpenClaw 实例，每个实例独立记忆
- 📝 **用户+助手消息** - 自动保存用户消息和 AI 回复
- 🔄 **去重** - 自动检测重复内容，避免重复存储
- 🎯 **相似度过滤** - 只返回相似度 >= 0.7 的结果

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
│   MySQL         │   Qdrant        │   sentence-           │
│  (结构化存储)    │  (向量数据库)    │   transformers       │
│                 │                 │  (语义向量)            │
└─────────────────┴─────────────────┴───────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   Admin UI (可选)   │
                   │   http://localhost:3000 │
                   └─────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker
- Docker Compose
- 建议 16GB+ 内存（用于 sentence-transformers 模型）

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

### 4. 访问管理界面

打开浏览器访问：http://localhost:3000

## 📡 API 接口

### 创建记忆

```bash
curl -X POST http://localhost:8000/api/memories \
  -H "Content-Type: application/json" \
  -H "X-API-Key: key-prod-1" \
  -d '{
    "content": "用户喜欢蓝色",
    "tags": ["preference", "color"],
    "agent_id": "memory-tester"
  }'
```

### 搜索记忆

```bash
# 向量语义搜索（推荐）
curl "http://localhost:8000/api/memories?q=用户偏好" \
  -H "X-API-Key: key-prod-1"

# 按 Agent 筛选
curl "http://localhost:8000/api/memories?agent_id=agent-1" \
  -H "X-API-Key: key-prod-1"
```

### 其他接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/memories | 搜索记忆（向量搜索+MySQL） |
| POST | /api/memories | 创建记忆（自动去重） |
| GET | /api/memories/{id} | 获取单条 |
| PUT | /api/memories/{id} | 更新记忆 |
| DELETE | /api/memories/{id} | 删除记忆 |
| GET | /api/stats | 获取统计信息 |

## ⚓ Hook 自动化

O-Mind 通过 Hook 实现自动化记忆管理：

| Hook | 触发时机 | 行为 |
|------|----------|------|
| `before_prompt_build` | 每次 LLM 调用前 | 自动检索相关记忆并注入上下文 |
| `agent_end` | Agent 完成后 | 自动保存用户消息和 AI 回复 |

### 配置 Hook

在 OpenClaw 配置中添加 plugin：

```json
{
  "plugins": {
    "entries": {
      "o-mind": {
        "enabled": true
      }
    }
  }
}
```

设置环境变量：

```bash
MEMORY_SERVER_URL=http://localhost:8000
MEMORY_API_KEY=key-prod-1
```

## 🔍 搜索原理（混合模式）

### 1. 向量语义搜索

- 使用 **bge-base-zh-v1.5** 生成 768 维语义向量
- 通过 **Qdrant** 向量数据库进行相似度匹配
- 只返回相似度 >= 0.7 的结果

### 2. 数据关联

- Qdrant 存储向量 + 元数据（instance_id, agent_id）
- MySQL 存储完整内容 + 标签 + 来源
- 搜索时：Qdrant → 返回 ID → MySQL 查询完整数据

### 3. 自动去重

- 每次保存前检查相同内容是否已存在
- 相同内容返回 `{"status": "duplicate"}` 不重复存储

### 4. 会话摘要自动注入

- 每小时自动生成会话摘要（使用 MiniMax M2.5）
- 搜索时自动将最新摘要放到结果最前面
- 摘要包含：主要话题、关键决策和解决方法、待处理事项

## 🌐 多实例配置

### 1. 配置 API Keys

在 docker-compose.yml 中设置环境变量：

```yaml
environment:
  - MEMORY_API_KEYS={"key-prod-1":{"instance_id":"prod-1","name":"生产环境"},"key-test-1":{"instance_id":"test-1","name":"测试环境"}}
```

### 2. OpenClaw 实例配置

每个 OpenClaw 实例配置不同的 API Key：

```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://o-mind-api:8000",
    "MEMORY_API_KEY": "key-prod-1"
  }
}
```

## 🐳 部署

### 开发环境

```bash
docker-compose up -d
```

### 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| O-Mind API | 8000 | REST API |
| Admin UI | 3000 | 管理界面 |
| MySQL | 3306 | 数据库 |
| Qdrant | 6333 | 向量数据库 |

### 更新服务

```bash
# 重新构建镜像
docker build -t o-mind:latest .

# 重启容器
docker restart o-mind-api
```

## 🛠️ 项目结构

```
O-Mind/
├── api/                      # FastAPI 服务
│   ├── main.py              # 主服务代码（含向量搜索、摘要注入）
│   └── summary_task.py       # 定时摘要任务
├── admin-ui/                 # React 管理界面
├── openclaw-plugin/          # OpenClaw Plugin
├── docker-compose.yml        # Docker Compose 配置
├── Dockerfile               # API 服务镜像
├── requirements.txt         # Python 依赖
└── README.md               # 项目说明
```

## 📋 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| MYSQL_HOST | MySQL 主机 | memory-mysql |
| QDRANT_HOST | Qdrant 主机 | memory-qdrant |
| MINIMAX_API_KEY | MiniMax API Key（用于摘要生成） | - |
| MEMORY_API_KEYS | 多实例 API Keys (JSON) | - |

## 📝 保存的内容

### 有价值的记忆

- ✅ 用户告诉的重要信息
- ✅ 运维配置和设置
- ✅ 项目背景和需求
- ✅ 问题和解决方案
- ✅ 工作摘要
- ✅ **自动生成的会话摘要**（每小时）

### 会话摘要

- 每小时自动总结会话内容
- 包含：主要话题、关键决策和解决方法、待处理事项
- 摘要会累积（每次新摘要基于上一次的摘要）
- 搜索时自动注入到上下文最前面

### 自动过滤

- ❌ 系统元数据（Conversation info、System:）
- ❌ 调试日志（Traceback、mysql:）
- ❌ 重复内容
- ❌ 相似度 < 0.7 的内容

## 🔧 故障排除

### 服务无法启动

```bash
# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

### 记忆未保存

```bash
# 检查 API 服务日志
docker logs o-mind-api

# 验证数据库连接
curl http://localhost:8000/health
```

### 向量搜索无结果

- 确认 Qdrant 有数据：`docker exec o-mind-api python -c "from api.main import get_qdrant_client; c = get_qdrant_client(); print(len(c.scroll('memories', limit=1000)[0]))"`
- 检查 MySQL 有数据：`docker exec o-mind-mysql mysql -uroot -p123456 -e "USE memory; SELECT COUNT(*) FROM memories;"`

## 📄 License

MIT License
