# O-Mind

> OpenClaw 本地记忆服务 - 私有化部署的长久会话和记忆解决方案

## ✨ 特性

- 🧠 **长久记忆** - 会话历史自动保存到本地数据库
- 🔒 **私有化部署** - 所有数据存储在本地服务器，安全可控
- ⚡ **自动化钩子** - 无需手动操作，自动完成记忆存取
- 🔍 **向量搜索** - 支持语义相似度搜索
- 📝 **会话摘要** - 每小时自动生成会话摘要，注入上下文
- 🗣️ **智能话题摘要** - 自动识别话题边界，生成话题维度的摘要
- 🔗 **跨会话关联** - 自动关联历史相关话题
- 🏷️ **关键信息提取** - 自动提取话题中的关键信息（人名、任务、决策等）
- 📊 **每日/每周报表** - 自动生成消费和使用报表
- 🐳 **Docker 部署** - 一键部署，支持 Docker Compose
- 🌐 **管理界面** - 可视化管理记忆和 Agent
- 🔑 **多实例隔离** - 支持多个 OpenClaw 实例，每个实例独立记忆
- 🔄 **去重** - 自动检测重复内容，避免重复存储

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenClaw Agent                          │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    O-Mind API Server                          │
│                  (FastAPI + Uvicorn)                         │
├─────────────────┬─────────────────┬───────────────────────┤
│   MySQL         │   Qdrant        │   摘要生成             │
│  (结构化存储)    │  (向量数据库)    │  (MiniMax LLM)       │
└─────────────────┴─────────────────┴───────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker
- Docker Compose
- 建议 4GB+ 内存

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

## 📡 API 接口

### 记忆管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/memories | 搜索记忆（向量搜索+MySQL） |
| POST | /api/memories | 创建记忆（自动去重） |
| GET | /api/memories/{id} | 获取单条 |
| PUT | /api/memories/{id} | 更新记忆 |
| DELETE | /api/memories/{id} | 删除记忆 |

### 话题管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/topics | 获取话题列表 |
| GET | /api/topics/{id} | 获取话题详情 |
| GET | /api/topics/{id}/relations | 获取关联话题 |
| GET | /api/topics/{id}/tree | 获取话题树 |
| POST | /api/topics/{id}/extract-keyinfo | 提取关键信息 |

### 报表

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/stats | 统计信息 |
| POST | /api/reports/daily | 生成日报 |
| POST | /api/reports/weekly | 生成周报 |
| POST | /api/reports/generate-all | 生成所有报表 |

## 🗣️ 智能话题系统

### 话题识别

O-Mind 自动识别对话中的话题边界：

- **同一任务连续对话** - 检测为同一话题
- **任务切换** - 通过"顺便"、"对了"、"回到"等关键词识别
- **子话题衍生** - 从主任务衍生出的子话题
- **跨会话关联** - 通过语义相似度关联历史话题

### 话题状态

| 状态 | 说明 |
|------|------|
| active | 进行中，有新消息 |
| paused | 暂停，超过2小时无新消息 |
| completed | 已完成 |
| archived | 已归档 |

### 话题摘要

- 每10条消息自动生成/更新摘要
- 支持增量续写（基于上一次摘要）
- 摘要包含：任务目标、当前进展、待解决问题、后续计划

### 关键信息提取

自动从话题中提取：
- 👤 人物（人名、角色）
- 📋 任务（待办事项、分配的任务）
- 💡 决策（关键决定、结论）
- 📎 关联（相关话题、依赖关系）

## 🏷️ 关键信息提取

### 提取类型

- **PERSON** - 人名、角色
- **TASK** - 任务、待办
- **DECISION** - 决策、结论
- **PROJECT** - 项目名称
- **ISSUE** - 问题、bug

### API 调用

```bash
curl -X POST http://localhost:8000/api/topics/{topic_id}/extract-keyinfo \
  -H "X-API-Key: key-prod-1"
```

### 返回示例

```json
{
  "persons": ["张三", "李四"],
  "tasks": ["优化数据库性能", "部署新功能"],
  "decisions": ["使用Redis缓存", "迁移到云服务器"],
  "projects": ["O-Mind项目", "OpenClaw平台"]
}
```

## 📊 报表系统

### 自动报表

- **日报** - 每日自动生成
- **周报** - 每周一自动生成
- **关键信息汇总** - 提取本周关键决策和任务

### 手动触发

```bash
# 生成日报
curl -X POST http://localhost:8000/api/reports/daily

# 生成周报
curl -X POST http://localhost:8000/api/reports/weekly

# 生成所有报表
curl -X POST http://localhost:8000/api/reports/generate-all
```

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

## 📄 License

MIT License
