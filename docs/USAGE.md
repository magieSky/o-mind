# O-Mind 使用手册

## 目录

1. [简介](#简介)
2. [快速开始](#快速开始)
3. [API 使用](#api-使用)
4. [管理界面](#管理界面)
5. [OpenClaw 集成](#openclaw-集成)
6. [Hook 配置](#hook-配置)
7. [多实例配置](#多实例配置)
8. [运维指南](#运维指南)
9. [常见问题](#常见问题)

---

## 1. 简介

### 什么是 O-Mind？

O-Mind 是 OpenClaw 的本地记忆服务，替代 mem9 的私有化部署方案。

### 核心功能

- ✅ 长久记忆存储
- ✅ 向量语义搜索（sentence-transformers）
- ✅ 自动化 Hook
- ✅ 私有化部署
- ✅ Docker 一键部署
- ✅ Web 管理界面
- ✅ 多实例隔离
- ✅ 用户+助手消息自动保存
- ✅ 语义向量去重

---

## 2. 快速开始

### 2.1 安装

```bash
# 克隆项目
git clone https://gitlab.bjhzsk.cn/develop/o-mind.git
cd o-mind

# 启动所有服务
docker-compose up -d
```

### 2.2 验证

```bash
# 检查服务状态
docker-compose ps

# 测试 API
curl http://localhost:8000/health
```

返回结果：
```json
{"status":"ok","service":"O-Mind","version":"2.0.0"}
```

### 2.3 访问管理界面

打开浏览器访问：**http://localhost:3000**

---

## 3. API 使用

### 3.1 创建记忆

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

响应：
```json
{
  "id": "uuid-xxx",
  "content": "用户喜欢蓝色",
  "tags": ["preference", "color"],
  "agent_id": "memory-tester",
  "instance_id": "prod-1",
  "created_at": "2026-03-16T12:00:00"
}
```

### 3.2 查询记忆

```bash
# 列出所有记忆（按时间倒序）
curl http://localhost:8000/api/memories \
  -H "X-API-Key: your-api-key"

# 向量语义搜索（推荐）
curl "http://localhost:8000/api/memories?q=用户偏好" \
  -H "X-API-Key: your-api-key"

# 按 Agent 筛选
curl "http://localhost:8000/api/memories?agent_id=agent-1" \
  -H "X-API-Key: your-api-key"

# 按标签筛选
curl "http://localhost:8000/api/memories?tags=preference" \
  -H "X-API-Key: your-api-key"
```

### 3.3 搜索原理（混合模式）

1. 使用 **sentence-transformers** (bge-base-zh) 生成查询向量（768维）
2. **Qdrant** 向量数据库进行相似度匹配
3. 返回匹配的 ID 列表
4. **MySQL** 查询完整记录

### 3.4 自动去重

- 每次保存前检查相同内容是否已存在
- 相同内容返回 `{"status": "duplicate"}`

### 3.3 更新记忆

```bash
curl -X PUT http://localhost:8000/api/memories/{id} \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"content": "新内容", "tags": ["new-tag"]}'
```

### 3.4 删除记忆

```bash
curl -X DELETE http://localhost:8000/api/memories/{id} \
  -H "X-API-Key: your-api-key"
```

### 3.5 获取实例信息

```bash
curl http://localhost:8000/api/instances/info \
  -H "X-API-Key: your-api-key"
```

### 3.6 列出所有 Agent

```bash
curl http://localhost:8000/api/agents \
  -H "X-API-Key: your-api-key"
```

---

## 4. 管理界面

### 4.1 访问

打开浏览器访问：**http://localhost:3000**

### 4.2 功能说明

| 功能 | 说明 |
|------|------|
| **实例切换** | 右上角选择不同 API Key，切换不同实例 |
| **记忆统计** | 显示记忆总数、本实例记忆数、Agent 数量 |
| **记忆列表** | 显示所有记忆，支持搜索 |
| **新建记忆** | 创建新的记忆条目 |
| **编辑记忆** | 修改现有记忆的内容和标签 |
| **删除记忆** | 删除指定记忆 |
| **Agent 管理** | 查看各 Agent 的记忆数量 |

### 4.3 操作步骤

1. **选择实例**：在右上角下拉框选择 API Key
2. **查看记忆**：在记忆管理页面查看所有记忆
3. **搜索记忆**：在搜索框输入关键词
4. **新建记忆**：点击"新建记忆"按钮
5. **编辑/删除**：点击对应记忆的编辑/删除按钮

---

## 5. OpenClaw 集成

### 5.1 配置 Skill

在 OpenClaw 的 `openclaw.json` 中添加：

```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://o-mind-api:8000",
    "MEMORY_API_KEY": "your-api-key"
  },
  "skills": {
    "paths": ["/workspace/skills"]
  }
}
```

### 5.2 部署 Skill

将 `skill-memory-server/` 目录复制到 OpenClaw 的 skills 目录。

### 5.3 使用

在对话中，Agent 会自动：
- 记住用户说的重要信息
- 检索与当前对话相关的记忆
- 在回答时参考历史记忆

---

## 6. Hook 配置

### 6.1 启用 Hook

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

### 6.2 Hook 类型

| Hook | 说明 | 自动化 |
|------|------|--------|
| before_prompt_build | 每次对话前检索相关记忆 | ✅ |
| agent_end | 对话结束后保存用户+助手消息 | ✅ |

### 6.3 保存的消息类型

- **user-message**: 用户说的话
- **assistant-message**: AI 的回复

### 6.4 自动过滤

以下内容不会被保存：
- 系统元数据（Conversation info、System:）
- 调试日志（Traceback、mysql:）
- 重复内容

---

## 7. 多实例配置

### 7.1 配置 API Keys

在 docker-compose.yml 中：

```yaml
services:
  o-mind-api:
    environment:
      - MEMORY_API_KEYS={"key-prod-1":{"instance_id":"prod-1","name":"生产环境"},"key-test-1":{"instance_id":"test-1","name":"测试环境"}}
```

### 7.2 为不同实例配置不同 Key

**生产环境 OpenClaw：**
```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://o-mind-api:8000",
    "MEMORY_API_KEY": "key-prod-1"
  }
}
```

**测试环境 OpenClaw：**
```json
{
  "env": {
    "MEMORY_SERVER_URL": "http://o-mind-api:8000",
    "MEMORY_API_KEY": "key-test-1"
  }
}
```

### 7.3 验证隔离

```bash
# 生产环境只能看到 prod 的记忆
curl http://localhost:8000/api/memories \
  -H "X-API-Key: key-prod-1"

# 测试环境只能看到 test 的记忆
curl http://localhost:8000/api/memories \
  -H "X-API-Key: key-test-1"
```

---

## 8. 运维指南

### 8.1 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 查看状态
docker-compose ps
```

### 8.2 数据备份

```bash
# 备份 MySQL 数据
docker exec o-mind-mysql mysqldump -uroot -p123456 memory > backup.sql

# 备份 Qdrant 数据
docker cp o-mind-qdrant:/qdrant/storage ./backup-qdrant
```

### 8.3 监控

```bash
# 检查 API 健康
curl http://localhost:8000/health

# 检查 MySQL
docker exec o-mind-mysql mysql -uroot -p123456 -e "SHOW DATABASES;"

# 检查 Qdrant
curl http://localhost:6333/health

# 检查管理界面
curl http://localhost:3000/
```

---

## 9. 常见问题

### Q1: 如何查看记忆数量？

```bash
curl http://localhost:8000/api/memories | jq length
```

### Q2: 如何删除所有记忆？

```bash
# 获取所有 ID 并删除
curl -s http://localhost:8000/api/memories \
  -H "X-API-Key: your-api-key" | jq -r '.[].id' | \
  xargs -I {} curl -X DELETE http://localhost:8000/api/memories/{} \
  -H "X-API-Key: your-api-key"
```

### Q3: 如何修改数据库密码？

1. 停止服务：`docker-compose down`
2. 修改 `.env` 文件中的密码
3. 重新启动：`docker-compose up -d`

### Q4: 管理界面显示空白？

1. 检查浏览器控制台是否有错误
2. 确认 Nginx 容器是否运行：`docker ps | grep admin`
3. 查看日志：`docker logs o-mind-admin`

### Q5: API 返回 401 错误？

确认 API Key 是否正确配置：
1. 检查 docker-compose.yml 中的 `MEMORY_API_KEYS` 环境变量
2. 确认请求头中是否正确传递 `X-API-Key`

### Q6: 如何扩展存储？

修改 `docker-compose.yml` 中的 volumes 配置：

```yaml
volumes:
  mysql_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/mysql
```

---

## 📞 支持

- 项目仓库：https://gitlab.bjhzsk.cn/develop/o-mind
- 问题反馈：https://gitlab.bjhzsk.cn/develop/o-mind/-/issues
