# O-Mind 使用手册

## 目录

1. [简介](#简介)
2. [快速开始](#快速开始)
3. [API 使用](#api-使用)
4. [OpenClaw 集成](#openclaw-集成)
5. [Hook 配置](#hook-配置)
6. [运维指南](#运维指南)
7. [常见问题](#常见问题)

---

## 1. 简介

### 什么是 O-Mind？

O-Mind 是 OpenClaw 的本地记忆服务，替代 mem9 的私有化部署方案。

### 核心功能

- ✅ 长久记忆存储
- ✅ 向量语义搜索
- ✅ 自动化 Hook
- ✅ 私有化部署
- ✅ Docker 一键部署

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
{"status":"ok","service":"memory-server"}
```

---

## 3. API 使用

### 3.1 创建记忆

```bash
curl -X POST http://localhost:8000/api/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户喜欢蓝色",
    "tags": ["preference", "color"],
    "source": "test"
  }'
```

响应：
```json
{
  "id": "uuid-xxx",
  "content": "用户喜欢蓝色",
  "tags": ["preference", "color"],
  "source": "test",
  "created_at": "2026-03-16T12:00:00"
}
```

### 3.2 查询记忆

```bash
# 列出所有记忆
curl http://localhost:8000/api/memories

# 关键词搜索
curl "http://localhost:8000/api/memories?q=喜欢"

# 标签筛选
curl "http://localhost:8000/api/memories?tags=preference"

# 向量语义搜索
curl "http://localhost:8000/api/memories/search/vector?query=用户偏好&limit=5"
```

### 3.3 高级查询

```bash
# 组合查询
curl "http://localhost:8000/api/memories?q=蓝色&tags=preference&limit=10&offset=0"
```

---

## 4. OpenClaw 集成

### 4.1 配置 Skill

在 OpenClaw 的 `openclaw.json` 中添加：

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

### 4.2 部署 Skill

将 `skill-memory-server/` 目录复制到 OpenClaw 的 skills 目录。

### 4.3 使用

在对话中，Agent 会自动：
- 记住用户说的重要信息
- 检索与当前对话相关的记忆
- 在回答时参考历史记忆

---

## 5. Hook 配置

### 5.1 启用 Hook

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

### 5.2 Hook 类型

| Hook | 说明 | 自动化 |
|------|------|--------|
| before_prompt_build | 每次对话前 | ✅ |
| before_reset | 重置会话前 | ✅ |
| agent_end | 对话结束后 | ✅ |

---

## 6. 运维指南

### 6.1 常用命令

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

### 6.2 数据备份

```bash
# 备份 MySQL 数据
docker exec o-mind-mysql mysqldump -uroot -p123456 memory > backup.sql

# 备份 Qdrant 数据
docker cp o-mind-qdrant:/qdrant/storage ./backup-qdrant
```

### 6.3 监控

```bash
# 检查 API 健康
curl http://localhost:8000/health

# 检查 MySQL
docker exec o-mind-mysql mysql -uroot -p123456 -e "SHOW DATABASES;"

# 检查 Qdrant
curl http://localhost:6333/health
```

---

## 7. 常见问题

### Q1: 如何查看记忆数量？

```bash
curl http://localhost:8000/api/memories | jq length
```

### Q2: 如何删除所有记忆？

```bash
# 获取所有 ID 并删除
curl -s http://localhost:8000/api/memories | jq -r '.[].id' | xargs -I {} curl -X DELETE http://localhost:8000/api/memories/{}
```

### Q3: 如何修改数据库密码？

1. 停止服务：`docker-compose down`
2. 修改 `.env` 文件中的密码
3. 重新启动：`docker-compose up -d`

### Q4: 如何扩展存储？

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
