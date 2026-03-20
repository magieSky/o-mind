"""
话题摘要服务
负责话题识别、创建、聚合和摘要生成
"""
import os
import json
import hashlib
import httpx
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from uuid import uuid4
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

# 话题配置
CONFIG = {
    "same_topic_max_gap": 600,        # 10分钟，同一话题最大时间间隔
    "new_session_min_gap": 1800,       # 30分钟，新会话最小时间间隔
    "auto_complete_idle": 7200,        # 2小时，自动标记完成的空闲时间
    "summary_message_count": 10,       # 每10条消息生成摘要
    "same_topic_threshold": 0.3,       # 向量相似度阈值
}

# 关键词配置
TASK_START_KEYWORDS = [
    "你去", "帮我", "麻烦", "请", "能不能",
    "处理一下", "看看", "查一下", "分析",
    "写个", "做个", "搞一下", "搞一搞", "优化"
]

TASK_SWITCH_KEYWORDS = [
    "顺便", "对了", "还有", "另外", "先这样",
    "回到", "换一个", "先处理", "先看看"
]

TASK_END_KEYWORDS = [
    "先这样", "先这样吧", "好了", "知道了",
    "没问题", "可以了", "完成", "结束"
]

EMERGENCY_KEYWORDS = ["报错", "错误", "故障", "挂了", "崩溃", "紧急", "出问题了"]


def get_db():
    """获取数据库连接"""
    return create_engine(DB_URL)


# ==================== 话题识别 ====================

def extract_group_id(agent_id: str) -> str:
    """从 agent_id 中提取群组 ID"""
    # 格式: agent:xxx:feishu:group:oc_xxx
    parts = agent_id.split(":")
    for i, part in enumerate(parts):
        if part == "group" and i + 1 < len(parts):
            return parts[i + 1]
    return "unknown"


def extract_session_id(agent_id: str, group_id: str) -> str:
    """生成会话 ID（按天）"""
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{agent_id}:{group_id}:{today}"


def detect_topic_boundary(content: str, time_gap: int) -> str:
    """
    检测话题边界
    返回: 'same' | 'new_task' | 'new_session'
    """
    # 1. 新会话检测
    if time_gap > CONFIG["new_session_min_gap"]:
        return "new_session"
    
    # 2. 新任务检测
    content_lower = content.lower()
    
    # 任务切换关键词
    if any(kw in content_lower for kw in TASK_SWITCH_KEYWORDS):
        return "new_task"
    
    # 任务结束关键词
    if any(kw in content_lower for kw in TASK_END_KEYWORDS):
        return "new_task"
    
    # 任务开始关键词（短消息且包含任务关键词）
    if len(content) < 200 and any(kw in content_lower for kw in TASK_START_KEYWORDS):
        return "new_task"
    
    # 3. 同一话题
    return "same"


def identify_topic_type(content: str) -> str:
    """
    识别话题类型
    返回: 'session' | 'task' | 'subtask' | 'emergency'
    """
    content_lower = content.lower()
    
    # 紧急话题
    if any(kw in content_lower for kw in EMERGENCY_KEYWORDS):
        return "emergency"
    
    # 子话题
    if any(kw in content_lower for kw in ["对了", "还有", "顺便", "另外"]):
        return "subtask"
    
    # 任务话题
    if any(kw in content_lower for kw in TASK_START_KEYWORDS):
        return "task"
    
    return "session"


def generate_topic_name(content: str, topic_type: str) -> str:
    """使用关键词生成话题名称"""
    content_lower = content.lower()
    
    # 根据类型和关键词生成名称
    if topic_type == "emergency":
        return "问题处理"
    
    keywords_map = {
        "优化": ["优化", "调整", "改进"],
        "部署": ["部署", "安装", "配置"],
        "前端": ["前端", "界面", "UI", "页面"],
        "数据库": ["数据库", "MySQL", "SQL", "查询"],
        "API": ["API", "接口", "调用"],
        "定时任务": ["定时", "cron", "调度"],
    }
    
    for name, kws in keywords_map.items():
        if any(kw in content_lower for kw in kws):
            return name
    
    # 默认名称
    return f"对话_{datetime.now().strftime('%H:%M')}"


# ==================== 话题管理 ====================

def get_or_create_topic(agent_id: str, content: str, timestamp: datetime) -> Tuple[str, bool]:
    """
    获取或创建话题
    返回: (topic_id, is_new)
    """
    engine = get_db()
    group_id = extract_group_id(agent_id)
    session_id = extract_session_id(agent_id, group_id)
    
    with engine.connect() as conn:
        # 1. 查找该会话最近的活跃话题
        result = conn.execute(text("""
            SELECT id, last_message_at, message_count, topic_type
            FROM topics 
            WHERE session_id = :session_id 
            AND status = 'active'
            ORDER BY last_message_at DESC
            LIMIT 1
        """), {"session_id": session_id})
        
        last_topic = result.fetchone()
        
        now = datetime.now()
        
        # 2. 如果有最近话题，检测是否需要创建新话题
        if last_topic:
            topic_id, last_time, msg_count, topic_type = last_topic
            
            # 计算时间间隔（秒）
            time_gap = (now - last_time).total_seconds() if last_time else 0
            
            # 检测话题边界
            boundary = detect_topic_boundary(content, time_gap)
            
            if boundary == "new_session":
                # 新会话，创建新话题
                new_topic_id = create_topic(agent_id, group_id, session_id, content)
                return new_topic_id, True
            
            elif boundary == "new_task":
                # 新任务，根据类型创建
                new_type = identify_topic_type(content)
                new_topic_id = create_topic(agent_id, group_id, session_id, content, 
                                           topic_type=new_type, parent_topic_id=topic_id)
                return new_topic_id, True
            
            else:
                # 同一话题，更新时间
                conn.execute(text("""
                    UPDATE topics 
                    SET last_message_at = :now,
                        message_count = message_count + 1
                    WHERE id = :topic_id
                """), {"now": now, "topic_id": topic_id})
                conn.commit()
                return topic_id, False
        
        else:
            # 3. 没有最近话题，创建新话题
            new_topic_id = create_topic(agent_id, group_id, session_id, content)
            return new_topic_id, True


def create_topic(agent_id: str, group_id: str, session_id: str, 
                 first_content: str, topic_type: str = "session",
                 parent_topic_id: str = None) -> str:
    """创建新话题"""
    engine = get_db()
    topic_id = str(uuid4())
    now = datetime.now()
    
    # 生成话题名称
    type_from_content = identify_topic_type(first_content)
    name = generate_topic_name(first_content, type_from_content)
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO topics (
                id, name, topic_type, status, session_id, parent_topic_id,
                message_count, user_message_count, started_at, last_message_at,
                agent_id, group_id, created_at, updated_at
            ) VALUES (
                :id, :name, :topic_type, 'active', :session_id, :parent_topic_id,
                1, 1, :now, :now, :agent_id, :group_id, :now, :now
            )
        """), {
            "id": topic_id,
            "name": name,
            "topic_type": topic_type,
            "session_id": session_id,
            "parent_topic_id": parent_topic_id,
            "agent_id": agent_id,
            "group_id": group_id,
            "now": now
        })
        conn.commit()
    
    print(f"[Topic] Created new topic: {topic_id} - {name}")
    return topic_id


def link_message_to_topic(topic_id: str, memory_id: str, role: str = "user"):
    """将消息关联到话题"""
    engine = get_db()
    
    with engine.connect() as conn:
        # 获取当前最大顺序
        result = conn.execute(text("""
            SELECT MAX(sequence_order) FROM topic_messages WHERE topic_id = :topic_id
        """), {"topic_id": topic_id})
        max_order = result.scalar() or 0
        
        conn.execute(text("""
            INSERT INTO topic_messages (id, topic_id, memory_id, role, sequence_order, created_at)
            VALUES (:id, :topic_id, :memory_id, :role, :order, :now)
        """), {
            "id": str(uuid4()),
            "topic_id": topic_id,
            "memory_id": memory_id,
            "role": role,
            "order": max_order + 1,
            "now": datetime.now()
        })
        conn.commit()


# ==================== 摘要生成 ====================

def get_topic_messages(topic_id: str, limit: int = 50) -> List[Dict]:
    """获取话题的所有消息"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT m.content, m.created_at, tm.role
            FROM topic_messages tm
            JOIN memories m ON tm.memory_id = m.id
            WHERE tm.topic_id = :topic_id
            ORDER BY tm.sequence_order ASC
            LIMIT :limit
        """), {"topic_id": topic_id, "limit": limit})
        
        return [
            {"content": row[0], "created_at": row[1], "role": row[2]}
            for row in result.fetchall()
        ]


def get_previous_summary(topic_id: str) -> str:
    """获取话题的上一次摘要"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT content FROM memories 
            WHERE topic_id = :topic_id 
            AND is_topic_summary = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """), {"topic_id": topic_id})
        
        row = result.fetchone()
        return row[0] if row else ""


def generate_summary_with_llm(messages: List[Dict], previous_summary: str = "", 
                              topic_name: str = "") -> str:
    """调用 LLM 生成话题摘要"""
    if not messages or not MINIMAX_API_KEY:
        return ""
    
    # 构建消息文本
    messages_text = "\n".join([
        f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}..."
        for m in messages[-20:]
    ])
    
    prompt = f"""你是一个会议摘要助手。请根据以下对话生成简洁的摘要。

{"上一次摘要：" + previous_summary + "\n\n" if previous_summary else ""}
对话内容：
{messages_text}

要求：
1. 如果有上一次摘要，基于它进行增量更新
2. 提取关键信息：任务目标、进展、问题、结论
3. 用中文回复
4. 摘要不超过300字

回复格式：
## {topic_name} 摘要
### 任务
...
### 进展
...
### 待办
..."""

    # 修复 f-string 中不能包含反斜杠的问题
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
                    {"role": "system", "content": "你是一个会议摘要助手，请用中文回复"},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return str(content) if content else ""
            
    except Exception as e:
        print(f"[Topic Summary] LLM call failed: {e}")
    
    return ""


def save_topic_summary(topic_id: str, summary: str):
    """保存话题摘要"""
    engine = get_db()
    topic_hash = hashlib.md5(topic_id.encode()).hexdigest()[:8]
    
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO memories (id, content, tags, source, agent_id, topic_id, 
                                is_topic_summary, created_at, updated_at)
            VALUES (:id, :content, :tags, :source, :agent_id, :topic_id, 
                    TRUE, :now, :now)
        """), {
            "id": f"topic-summary-{topic_hash}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "content": summary,
            "tags": '["topic-summary", "auto"]',
            "source": "topic-summary",
            "agent_id": "system",
            "topic_id": topic_id,
            "now": datetime.now()
        })
        
        # 更新话题的摘要字段
        conn.execute(text("""
            UPDATE topics 
            SET summary = :summary,
                summary_version = summary_version + 1,
                updated_at = :now
            WHERE id = :topic_id
        """), {"summary": summary, "topic_id": topic_id, "now": datetime.now()})
        
        conn.commit()


def check_and_generate_summary(topic_id: str) -> bool:
    """检查并生成话题摘要"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT message_count, summary_version FROM topics WHERE id = :topic_id
        """), {"topic_id": topic_id})
        row = result.fetchone()
        
        if not row:
            return False
        
        message_count, summary_version = row
        
        # 达到摘要触发条件
        if message_count >= CONFIG["summary_message_count"]:
            # 获取话题名称
            result = conn.execute(text("""
                SELECT name FROM topics WHERE id = :topic_id
            """), {"topic_id": topic_id})
            name_row = result.fetchone()
            topic_name = name_row[0] if name_row else "对话"
            
            # 生成摘要
            messages = get_topic_messages(topic_id)
            previous = get_previous_summary(topic_id)
            summary = generate_summary_with_llm(messages, previous, topic_name)
            
            if summary:
                save_topic_summary(topic_id, summary)
                print(f"[Topic] Generated summary for topic: {topic_id}")
                return True
    
    return False


# ==================== 对外接口 ====================

def process_message(agent_id: str, content: str, memory_id: str, role: str = "user"):
    """
    处理新消息：识别话题并关联
    """
    now = datetime.now()
    
    # 1. 获取或创建话题
    topic_id, is_new = get_or_create_topic(agent_id, content, now)
    
    # 2. 关联消息到话题
    link_message_to_topic(topic_id, memory_id, role)
    
    # 3. 检查是否需要生成摘要
    check_and_generate_summary(topic_id)
    
    return topic_id


if __name__ == "__main__":
    # 测试
    print("[Topic Service] Testing...")
    topic_id, is_new = get_or_create_topic(
        "agent:openclaw-admin:feishu:group:oc_xxx",
        "小O，你帮我优化下o-mind的部署",
        datetime.now()
    )
    print(f"Topic: {topic_id}, New: {is_new}")
