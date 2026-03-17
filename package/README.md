# O-Mind

> OpenClaw 本地记忆服务 - 私有化部署的长久会话和记忆解决方案

## ✨ 特性

- 🧠 **长久记忆** - 会话历史自动保存到本地数据库
- 🔒 **私有化部署** - 所有数据存储在本地服务器，安全可控
- ⚡ **自动化钩子** - 无需手动操作，自动完成记忆存取
- 🔍 **向量搜索** - 支持语义相似度搜索
- 🐳 **Docker 部署** - 一键部署，支持 Docker Compose
- 🌐 **管理界面** - 可视化管理记忆和 Agent
- 🔑 **多实例隔离** - 支持多个 OpenClaw 实例，每个实例独立记忆

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
  -H "X-API-Key: your-api-key" \
  -d '{
    "content": "用户喜欢蓝色",
    "tags": ["preference", "color"],
    "agent_id": "memory-tester"
  }'
```

### 搜索记忆

```bash
# 关键词搜索
curl "http://localhost:8000/api/memories?q=喜欢" \
  -H "X-API-Key: your-api-key"

# 按 Agent 筛选
curl "http://localhost:8000/api/memories?agent_id=agent-1" \
  -H "X-API-Key: your-api-key"
```

### 其他接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/memories | 搜索记忆 |
| GET | /api/memories/{id} | 获取单条 |
| PUT | /api/memories/{id} | 更新记忆 |
| DELETE | /api/memories/{id} | 删除记忆 |
| GET | /api/instances/info | 获取实例信息 |
| GET | /api/agents | 列出所有 Agent |

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

## 🎨 管理界面

### 访问地址

http://localhost:3000

### 功能

| 功能 | 说明 |
|------|------|
| 📊 记忆统计 | 总数量、本实例数量、Agent 数量 |
| 🔍 记忆搜索 | 关键词搜索 |
| ➕ 新建记忆 | 创建新记忆 |
| ✏️ 编辑记忆 | 修改内容和标签 |
| 🗑️ 删除记忆 | 删除记忆 |
| 👥 Agent 管理 | 查看各 Agent 的记忆统计 |
| 🔑 实例切换 | 通过 API Key 切换不同实例 |

### 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  O-Mind 管理面板                    [key-prod-1 ▼]          │
├──────────┬──────────────────────────────────────────────────┤
│ 记忆管理  │  记忆总数: 5    本实例记忆: 5    Agent: 2       │
│ Agent管理 │ ───────────────────────────────────────────────  │
│   设置    │  内容                    标签    Agent   操作    │
│          │  用户喜欢蓝色           蓝色    agent-1  编辑删除 │
│          │  用户喜欢绿色           绿色    agent-2  编辑删除 │
└──────────┴──────────────────────────────────────────────────┘
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
| Admin UI | 3000 | 管理界面 |
| MySQL | 3306 | 数据库 |
| Qdrant | 6333 | 向量数据库 |

## 🛠️ 项目结构

```
O-Mind/
├── api/                      # FastAPI 服务
│   └── main.py              # 主服务代码
├── admin-ui/                 # React 管理界面
│   ├── src/
│   │   └── App.jsx         # 主组件
│   └── nginx.conf          # Nginx 配置
├── skill-memory-server/      # OpenClaw Skill
├── hooks/                    # Hook 自动化
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

### 管理界面空白

```bash
# 检查 Nginx 日志
docker logs o-mind-admin

# 确认 API 代理配置
docker exec o-mind-admin cat /etc/nginx/conf.d/default.conf
```

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
