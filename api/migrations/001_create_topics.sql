-- O-Mind 话题摘要系统数据库迁移
-- 创建时间: 2026-03-20
-- 分支: feature/topic-summary

-- 1. 创建话题表
CREATE TABLE IF NOT EXISTS topics (
    id VARCHAR(36) PRIMARY KEY,
    
    -- 话题元信息
    name VARCHAR(255),                    
    topic_type VARCHAR(20) DEFAULT 'session',
    status VARCHAR(20) DEFAULT 'active',
    
    -- 层级关系
    session_id VARCHAR(36),
    parent_topic_id VARCHAR(36),
    
    -- 消息聚合
    message_count INT DEFAULT 0,
    user_message_count INT DEFAULT 0,
    
    -- 时间信息
    started_at DATETIME,
    last_message_at DATETIME,
    completed_at DATETIME,
    
    -- 摘要
    summary TEXT,
    summary_version INT DEFAULT 1,
    
    -- 上下文（用于跨会话关联）
    keywords JSON,
    context_embedding JSON,
    
    -- 关联
    agent_id VARCHAR(255),
    group_id VARCHAR(255),
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parent_topic_id) REFERENCES topics(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 索引
CREATE INDEX idx_topics_session ON topics(session_id);
CREATE INDEX idx_topics_parent ON topics(parent_topic_id);
CREATE INDEX idx_topics_status ON topics(status);
CREATE INDEX idx_topics_agent_group ON topics(agent_id, group_id);
CREATE INDEX idx_topics_started ON topics(started_at);

-- 2. 创建话题消息关联表
CREATE TABLE IF NOT EXISTS topic_messages (
    id VARCHAR(36) PRIMARY KEY,
    topic_id VARCHAR(36) NOT NULL,
    memory_id VARCHAR(36) NOT NULL,
    role VARCHAR(20),
    sequence_order INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE INDEX idx_topic_messages_topic ON topic_messages(topic_id);
CREATE INDEX idx_topic_messages_order ON topic_messages(topic_id, sequence_order);
CREATE INDEX idx_topic_messages_memory ON topic_messages(memory_id);

-- 3. 修改 memories 表，添加话题字段
ALTER TABLE memories ADD COLUMN topic_id VARCHAR(36);
ALTER TABLE memories ADD COLUMN topic_type VARCHAR(20);
ALTER TABLE memories ADD COLUMN is_topic_summary BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_memories_topic ON memories(topic_id);
