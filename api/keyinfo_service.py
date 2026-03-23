"""
关键信息提取服务
从对话中提取目标、结论、位置等关键信息
"""
import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# 数据库配置
MYSQL_HOST = os.getenv("MYSQL_HOST", "memory-mysql")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "memory")

DB_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

# MiniMax API 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"


def get_db():
    return create_engine(DB_URL)


# ==================== 关键信息提取 ====================

EXTRACT_PROMPT = """从以下对话中提取关键信息：

## 对话内容
{content}

## 提取要求
请提取以下信息，以 JSON 格式返回：

{{
    "goal": "本次对话的目标或任务（一句话）",
    "conclusion": "形成的结论或决定，如果没有则写"无"",
    "locations": [
        {{"type": "文件|配置|服务", "path": "路径", "description": "说明"}}
    ],
    "next_steps": ["下一步需要做的事项"],
    "status": "completed | in_progress | pending"
}}

注意：
- goal: 用户最初的目标或任务
- conclusion: 最终达成的结论，如果没有则写"无"
- locations: 涉及的所有文件/配置/服务路径
- next_steps: 还需要做的事情
- status: 当前状态

直接返回 JSON，不要其他内容。"""


def extract_key_info(messages: List[Dict]) -> Dict:
    """使用 LLM 从对话中提取关键信息"""
    if not messages or not MINIMAX_API_KEY:
        return {}
    
    # 拼接对话内容
    content = "\n".join([
        f"{'用户' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')[:300]}..."
        for m in messages[-20:]  # 只用最近20条
    ])
    
    prompt = EXTRACT_PROMPT.format(content=content)
    
    api_url = f"{MINIMAX_BASE_URL}/text/chatcompletion_v2"
    
    try:
        response = httpx.post(
            api_url,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": "MiniMax-M2.5",
                "messages": [
                    {"role": "system", "content": "你是一个信息提取助手，请从对话中提取关键信息，直接返回 JSON。"},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 尝试解析 JSON
            if content:
                # 去除可能的 markdown 代码块
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                result = json.loads(content.strip())
                return result
                
    except Exception as e:
        print(f"[KeyInfo] LLM extraction failed: {e}")
    
    return {}


def save_key_info(topic_id: str, key_info: Dict):
    """保存关键信息到话题"""
    if not key_info:
        return
    
    engine = get_db()
    
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE topics 
            SET key_info = :key_info,
                updated_at = :now
            WHERE id = :topic_id
        """), {
            "key_info": json.dumps(key_info, ensure_ascii=False),
            "topic_id": topic_id,
            "now": datetime.now()
        })
        conn.commit()
    
    print(f"[KeyInfo] Saved key info for topic: {topic_id}")


def extract_and_save_key_info(topic_id: str) -> Dict:
    """提取并保存话题的关键信息"""
    from api.topic_service import get_topic_messages
    
    messages = get_topic_messages(topic_id, limit=20)
    key_info = extract_key_info(messages)
    
    if key_info:
        save_key_info(topic_id, key_info)
    
    return key_info


# ==================== 日报/周报生成 ====================

DAILY_REPORT_PROMPT = """请根据以下对话记录生成今日工作日报：

## 对话记录
{content}

## 日报格式
## {date} 工作日报

### 完成事项
- 

### 遇到问题
- 

### 待处理
- 

请用中文回复，按照格式填写内容。"""

WEEKLY_REPORT_PROMPT = """请根据以下对话记录生成本周工作周报：

## 对话记录
{content}

## 周报格式
## 第{week}周工作周报 ({start_date} ~ {end_date})

### 本周完成
- 

### 遇到问题
- 

### 下周计划
- 

请用中文回复，按照格式填写内容。"""


def get_agent_memories(agent_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
    """获取指定 Agent 在日期范围内的记忆"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, content, created_at, tags
            FROM memories 
            WHERE agent_id = :agent_id
            AND created_at BETWEEN :start AND :end
            ORDER BY created_at DESC
            LIMIT 100
        """), {
            "agent_id": agent_id,
            "start": start_date,
            "end": end_date
        })
        
        return [
            {"id": row[0], "content": row[1], "created_at": row[2], "tags": row[3]}
            for row in result.fetchall()
        ]


def generate_daily_report(agent_id: str, date: datetime = None) -> str:
    """生成日报"""
    if date is None:
        date = datetime.now()
    
    start = datetime(date.year, date.month, date.day, 0, 0, 0)
    end = start + timedelta(days=1)
    
    memories = get_agent_memories(agent_id, start, end)
    
    if not memories:
        return f"## {date.strftime('%Y-%m-%d')} 工作日报\n\n无工作记录"
    
    content = "\n".join([
        f"[{m['created_at'].strftime('%H:%M')}] {m['content'][:200]}"
        for m in memories[:50]
    ])
    
    prompt = DAILY_REPORT_PROMPT.format(content=content, date=date.strftime('%Y-%m-%d'))
    
    return call_llm(prompt)


def generate_weekly_report(agent_id: str, week: int = None) -> str:
    """生成周报"""
    if week is None:
        # 计算当前周
        today = datetime.now()
        week = (today.day - 1) // 7 + 1
    
    # 计算本周开始和结束日期
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    memories = get_agent_memories(agent_id, start_of_week, end_of_week)
    
    if not memories:
        return f"## 第{week}周工作周报\n\n本周无工作记录"
    
    content = "\n".join([
        f"[{m['created_at'].strftime('%m-%d %H:%M')}] {m['content'][:200]}"
        for m in memories[:100]
    ])
    
    prompt = WEEKLY_REPORT_PROMPT.format(
        content=content,
        week=week,
        start_date=start_of_week.strftime('%Y-%m-%d'),
        end_date=end_of_week.strftime('%Y-%m-%d')
    )
    
    return call_llm(prompt)


def call_llm(prompt: str) -> str:
    """调用 LLM 生成内容"""
    if not MINIMAX_API_KEY:
        return "未配置 MiniMax API Key"
    
    api_url = f"{MINIMAX_BASE_URL}/text/chatcompletion_v2"
    
    try:
        response = httpx.post(
            api_url,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": "MiniMax-M2.5",
                "messages": [
                    {"role": "system", "content": "你是一个工作周报助手，请用中文回复。"},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return str(content) if content else "生成失败"
            
    except Exception as e:
        print(f"[Report] LLM call failed: {e}")
    
    return "生成失败"


def save_report(agent_id: str, report_type: str, content: str) -> str:
    """保存报告到记忆"""
    import hashlib
    
    engine = get_db()
    report_id = f"{report_type}-{hashlib.md5(content.encode()).hexdigest()[:8]}"
    
    with engine.connect() as conn:
        # 获取 instance_id
        result = conn.execute(text("""
            SELECT DISTINCT instance_id FROM memories WHERE agent_id = :agent_id LIMIT 1
        """), {"agent_id": agent_id})
        row = result.fetchone()
        instance_id = row[0] if row else "default"
        
        conn.execute(text("""
            INSERT INTO memories (id, content, tags, source, agent_id, instance_id, created_at, updated_at)
            VALUES (:id, :content, :tags, :source, :agent_id, :instance_id, :now, :now)
        """), {
            "id": report_id,
            "content": content,
            "tags": f'["{report_type}", "auto-generated"]',
            "source": f"{report_type}-generator",
            "agent_id": agent_id,
            "instance_id": instance_id,
            "now": datetime.now()
        })
        conn.commit()
    
    print(f"[Report] Saved {report_type} report for {agent_id}")
    return report_id


# ==================== 定时任务 ====================

def run_daily_report_task():
    """生成所有 Agent 的日报"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT agent_id FROM memories WHERE agent_id IS NOT NULL
        """))
        agent_ids = [row[0] for row in result.fetchall()]
    
    for agent_id in agent_ids:
        print(f"[Report] Generating daily report for {agent_id}")
        report = generate_daily_report(agent_id)
        if report and "生成失败" not in report:
            save_report(agent_id, "daily-report", report)


def run_weekly_report_task():
    """生成所有 Agent 的周报"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT agent_id FROM memories WHERE agent_id IS NOT NULL
        """))
        agent_ids = [row[0] for row in result.fetchall()]
    
    for agent_id in agent_ids:
        print(f"[Report] Generating weekly report for {agent_id}")
        report = generate_weekly_report(agent_id)
        if report and "生成失败" not in report:
            save_report(agent_id, "weekly-report", report)


if __name__ == "__main__":
    # 测试
    print("[KeyInfo] Testing...")
    
    # 测试提取
    test_messages = [
        {"role": "user", "content": "小O，你帮我开发一个话题摘要系统"},
        {"role": "assistant", "content": "好的，我来设计并开发这个功能"},
        {"role": "user", "content": "完成后部署到服务器上"},
        {"role": "assistant", "content": "已部署完成，服务运行在 localhost:8000"}
    ]
    
    result = extract_key_info(test_messages)
    print(f"Extracted: {result}")
