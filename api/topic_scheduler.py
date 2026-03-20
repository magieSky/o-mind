"""
话题摘要定时任务
"""
import os
import json
from datetime import datetime, timedelta
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

CONFIG = {
    "summary_message_count": 10,
    "auto_complete_idle": 7200,  # 2小时
}


def get_db():
    return create_engine(DB_URL)


def check_and_generate_summaries():
    """检查所有活跃话题，生成需要更新的摘要"""
    engine = get_db()
    
    with engine.connect() as conn:
        # 1. 检查需要生成摘要的话题（消息数达到阈值）
        result = conn.execute(text("""
            SELECT id, name, message_count 
            FROM topics 
            WHERE status = 'active' 
            AND message_count >= :threshold
            AND (summary IS NULL OR summary = '')
        """), {"threshold": CONFIG["summary_message_count"]})
        
        topics_need_summary = result.fetchall()
        
        for topic in topics_need_summary:
            topic_id, name, count = topic
            print(f"[Topic Scheduler] Topic {topic_id} ({name}) has {count} messages, needs summary")
            
            # 获取消息并生成摘要
            from api.topic_service import get_topic_messages, get_previous_summary, generate_summary_with_llm, save_topic_summary
            
            messages = get_topic_messages(topic_id)
            previous = get_previous_summary(topic_id)
            summary = generate_summary_with_llm(messages, previous, name or "对话")
            
            if summary:
                save_topic_summary(topic_id, summary)
                print(f"[Topic Scheduler] Generated summary for topic {topic_id}")
        
        # 2. 检查需要标记为完成的话题（长时间无新消息）
        idle_threshold = datetime.now() - timedelta(seconds=CONFIG["auto_complete_idle"])
        
        conn.execute(text("""
            UPDATE topics 
            SET status = 'completed',
                completed_at = NOW()
            WHERE status = 'active' 
            AND last_message_at < :idle_threshold
        """), {"idle_threshold": idle_threshold})
        
        completed = conn.rowcount
        if completed > 0:
            print(f"[Topic Scheduler] Marked {completed} topics as completed")
        
        conn.commit()


def run_topic_scheduler():
    """运行话题定时检查"""
    print(f"[Topic Scheduler] Running at {datetime.now()}")
    try:
        check_and_generate_summaries()
    except Exception as e:
        print(f"[Topic Scheduler] Error: {e}")


if __name__ == "__main__":
    run_topic_scheduler()
