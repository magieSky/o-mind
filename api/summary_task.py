"""
定时摘要任务 - 每小时总结会话
"""
import os
import httpx
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# 数据库连接
MYSQL_HOST = os.getenv("MYSQL_HOST", "memory-mysql")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "memory")

# MiniMax API 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"

DB_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

def get_db():
    return create_engine(DB_URL)

def get_recent_messages_by_agent(hours=1):
    """按 agent 分组获取最近1小时的消息"""
    engine = get_db()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT agent_id, content, created_at 
            FROM memories 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL :hours HOUR)
            AND (tags NOT LIKE '%summary%' OR tags IS NULL)
            AND agent_id IS NOT NULL
            ORDER BY created_at DESC
        """), {"hours": hours})
        rows = result.fetchall()
    
    # 按 agent_id 分组
    by_agent = {}
    for row in rows:
        agent_id = row[0]
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append({"content": row[1], "agent_id": row[0], "created_at": row[2]})
    
    return by_agent

def get_previous_summary(agent_id: str):
    """获取指定 agent 的上一次摘要"""
    engine = get_db()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT content 
            FROM memories 
            WHERE agent_id = :agent_id
            AND tags LIKE '%summary%'
            ORDER BY created_at DESC
            LIMIT 1
        """), {"agent_id": agent_id})
        row = result.fetchone()
        return row[0] if row else ""

def generate_summary(messages: list, previous_summary: str = "") -> str:
    """调用 MiniMax 生成摘要（包含上次的摘要）"""
    if not messages:
        return ""
    
    # 构造 prompt
    prompt = ""
    
    # 如果有上次摘要，先加入
    if previous_summary:
        prompt += f"""以下是上一次的会话摘要（包含之前的问题解决方法）：

{previous_summary}

---
"""
    
    prompt += f"""请总结最近1小时的对话要点：

"""
    for i, msg in enumerate(messages[-20:], 1):
        prompt += f"{i}. {msg['content'][:100]}...\n"
    
    prompt += """

请总结：
1. 主要话题
2. 关键决策和解决方法
3. 待处理事项
"""
    
    if not MINIMAX_API_KEY:
        print("[Summary] No MINIMAX_API_KEY configured")
        return ""
    
    try:
        response = httpx.post(
            f"{MINIMAX_BASE_URL}/text/chatcompletion_v2",
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": "MiniMax-M2.5",
                "messages": [
                    {"role": "system", "content": "你是一个会议摘要助手，请用中文回复"},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            # 确保 UTF-8 编码
            return str(content) if content else ""
    except Exception as e:
        print(f"[Summary] MiniMax API call failed: {e}")
    except Exception as e:
        print(f"[Summary] MiniMax API call failed: {e}")
    
    return ""

import hashlib

def save_summary(summary: str, agent_id: str = "system"):
    """保存摘要到数据库"""
    if not summary:
        return
    
    # 用 hash 缩短 agent_id
    agent_hash = hashlib.md5(agent_id.encode()).hexdigest()[:8] if agent_id else "system"
    
    engine = get_db()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO memories (id, content, tags, source, agent_id, created_at, updated_at)
            VALUES (:id, :content, :tags, :source, :agent_id, NOW(), NOW())
        """), {
            "id": f"summary-{agent_hash}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "content": summary,
            "tags": '["summary", "hourly"]',
            "source": "auto-summary",
            "agent_id": agent_id
        })
        conn.commit()

def run_hourly_summary():
    """每小时运行一次（按 agent 维度）"""
    print(f"[{datetime.now()}] Running hourly summary...")
    
    # 按 agent 分组获取消息
    messages_by_agent = get_recent_messages_by_agent(hours=1)
    print(f"[Summary] Found {len(messages_by_agent)} agents with messages")
    
    for agent_id, messages in messages_by_agent.items():
        print(f"[Summary] Processing agent: {agent_id}, {len(messages)} messages")
        
        # 获取该 agent 的上次摘要
        previous_summary = get_previous_summary(agent_id)
        
        # 生成摘要
        summary = generate_summary(messages, previous_summary)
        if summary:
            # 保存摘要（带 agent_id）
            save_summary(summary, agent_id=agent_id)
            print(f"[Summary] Saved for {agent_id}: {summary[:50]}...")

if __name__ == "__main__":
    run_hourly_summary()
