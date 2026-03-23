"""
向量服务 - 提供语义相似度计算和跨会话话题关联
"""
import os
import json
import hashlib
import httpx
from datetime import datetime
from typing import List, Dict, Tuple, Optional
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

# 向量配置
CONFIG = {
    "embedding_model": "abab6.5s-chat",
    "similarity_threshold": 0.75,       # 相似度阈值，超过则关联
    "max_related_topics": 3,           # 最多关联的话题数
    "min_messages_for_cluster": 5,     # 最少消息数才参与聚类
}


def get_db():
    return create_engine(DB_URL)


# ==================== Embedding 计算 ====================

def get_embedding(text: str) -> Optional[List[float]]:
    """调用 MiniMax API 获取文本的 embedding"""
    if not MINIMAX_API_KEY:
        print("[Vector] No MINIMAX_API_KEY, skip embedding")
        return None
    
    api_url = f"{MINIMAX_BASE_URL}/embeddings"
    
    try:
        response = httpx.post(
            api_url,
            headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": CONFIG["embedding_model"],
                "text": text[:8192]  # 限制长度
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data.get("data", [{}])[0].get("embedding", [])
            return embedding
        else:
            print(f"[Vector] Embedding API error: {response.status_code}")
            
    except Exception as e:
        print(f"[Vector] Embedding failed: {e}")
    
    return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """计算余弦相似度"""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


# ==================== 话题向量存储 ====================

def save_topic_embedding(topic_id: str, embedding: List[float]):
    """保存话题的向量表示"""
    engine = get_db()
    embedding_json = json.dumps(embedding)
    topic_hash = hashlib.md5(topic_id.encode()).hexdigest()[:8]
    
    with engine.connect() as conn:
        # 检查是否已存在
        result = conn.execute(text("""
            SELECT id FROM topic_embeddings WHERE topic_id = :topic_id
        """), {"topic_id": topic_id})
        
        if result.fetchone():
            # 更新
            conn.execute(text("""
                UPDATE topic_embeddings 
                SET embedding = :embedding, updated_at = :now
                WHERE topic_id = :topic_id
            """), {"embedding": embedding_json, "topic_id": topic_id, "now": datetime.now()})
        else:
            # 插入
            conn.execute(text("""
                INSERT INTO topic_embeddings (id, topic_id, embedding, created_at, updated_at)
                VALUES (:id, :topic_id, :embedding, :now, :now)
            """), {
                "id": f"emb-{topic_hash}",
                "topic_id": topic_id,
                "embedding": embedding_json,
                "now": datetime.now()
            })
        
        conn.commit()


def get_topic_embedding(topic_id: str) -> Optional[List[float]]:
    """获取话题的向量表示"""
    engine = get_db()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT embedding FROM topic_embeddings WHERE topic_id = :topic_id
        """), {"topic_id": topic_id})
        
        row = result.fetchone()
        if row:
            return json.loads(row[0])
    
    return None


def generate_topic_embedding(topic_id: str, messages: List[Dict]) -> Optional[List[float]]:
    """为主题生成向量表示（基于消息内容）"""
    if not messages:
        return None
    
    # 拼接消息内容
    combined_text = "\n".join([
        f"{m.get('content', '')[:200]}" 
        for m in messages[-10:]  # 只用最近10条消息
    ])
    
    return get_embedding(combined_text)


# ==================== 跨会话话题关联 ====================

def find_related_topics(agent_id: str, content: str, exclude_topic_id: str = None) -> List[Dict]:
    """
    查找与当前内容相关的历史话题
    返回: [(topic_id, similarity, topic_name, last_message_at)]
    """
    # 1. 获取当前内容的 embedding
    current_embedding = get_embedding(content)
    if not current_embedding:
        # 如果没有 embedding API，使用关键词匹配
        return find_related_by_keywords(agent_id, content, exclude_topic_id)
    
    engine = get_db()
    
    # 提取群组 ID
    group_id = None
    parts = agent_id.split(":")
    for i, part in enumerate(parts):
        if part == "group" and i + 1 < len(parts):
            group_id = parts[i + 1]
            break
    
    with engine.connect() as conn:
        # 查询同一 agent+group 的历史活跃/已完成话题
        query = """
            SELECT t.id, t.name, t.last_message_at, te.embedding,
                   t.message_count, t.status
            FROM topics t
            LEFT JOIN topic_embeddings te ON t.id = te.topic_id
            WHERE t.agent_id = :agent_id
        """
        params = {"agent_id": agent_id}
        
        if group_id:
            query += " AND t.group_id = :group_id"
            params["group_id"] = group_id
        
        if exclude_topic_id:
            query += " AND t.id != :exclude_topic_id"
            params["exclude_topic_id"] = exclude_topic_id
        
        # 只查询有向量的话题
        query += " AND te.embedding IS NOT NULL"
        
        # 排除当前正在讨论的话题
        query += " AND t.status IN ('active', 'completed')"
        
        # 限制数量
        query += " LIMIT 20"
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
    # 2. 计算相似度
    related_topics = []
    for row in rows:
        topic_id, name, last_time, embedding_json, message_count, status = row
        
        if not embedding_json:
            continue
        
        try:
            topic_embedding = json.loads(embedding_json)
            similarity = cosine_similarity(current_embedding, topic_embedding)
            
            if similarity >= CONFIG["similarity_threshold"]:
                related_topics.append({
                    "topic_id": topic_id,
                    "topic_name": name,
                    "similarity": round(similarity, 3),
                    "last_message_at": last_time,
                    "message_count": message_count,
                    "status": status
                })
        except:
            continue
    
    # 3. 排序并返回
    related_topics.sort(key=lambda x: x["similarity"], reverse=True)
    return related_topics[:CONFIG["max_related_topics"]]


def find_related_by_keywords(agent_id: str, content: str, exclude_topic_id: str = None) -> List[Dict]:
    """使用关键词查找相关话题（无 embedding 时的降级方案）"""
    import re
    
    # 提取关键词
    keywords = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', content.lower())
    
    if not keywords:
        return []
    
    engine = get_db()
    
    with engine.connect() as conn:
        # 查询相关话题
        result = conn.execute(text("""
            SELECT id, name, last_message_at, message_count, status
            FROM topics
            WHERE agent_id = :agent_id
            AND status IN ('active', 'completed')
            AND id != :exclude_topic_id
            ORDER BY last_message_at DESC
            LIMIT 20
        """), {"agent_id": agent_id, "exclude_topic_id": exclude_topic_id or ""})
        
        rows = result.fetchall()
    
    # 简单关键词匹配
    related = []
    for row in rows:
        topic_id, name, last_time, message_count, status = row
        name_lower = name.lower() if name else ""
        
        # 计算关键词匹配数
        match_count = sum(1 for kw in keywords if kw in name_lower or kw in content.lower())
        
        if match_count >= 1:
            related.append({
                "topic_id": topic_id,
                "topic_name": name,
                "similarity": match_count / len(keywords),
                "last_message_at": last_time,
                "message_count": message_count,
                "status": status
            })
    
    related.sort(key=lambda x: x["similarity"], reverse=True)
    return related[:CONFIG["max_related_topics"]]


def link_to_related_topic(current_topic_id: str, related_topics: List[Dict]):
    """将相关话题关联到当前话题"""
    if not related_topics:
        return
    
    engine = get_db()
    
    with engine.connect() as conn:
        for related in related_topics:
            topic_id = related["topic_id"]
            similarity = related["similarity"]
            
            # 插入关联关系
            try:
                conn.execute(text("""
                    INSERT IGNORE INTO topic_relations 
                    (id, source_topic_id, target_topic_id, similarity, created_at)
                    VALUES (:id, :source, :target, :similarity, :now)
                """), {
                    "id": f"rel-{current_topic_id[:8]}-{topic_id[:8]}",
                    "source": current_topic_id,
                    "target": topic_id,
                    "similarity": similarity,
                    "now": datetime.now()
                })
            except:
                pass
        
        conn.commit()


# ==================== 话题聚类 ====================

def cluster_similar_topics(agent_id: str, group_id: str = None) -> List[List[str]]:
    """
    对话题进行聚类，将相似的话题归为一组
    返回: [[topic_id, topic_id, ...], [topic_id, ...]]
    """
    engine = get_db()
    
    with engine.connect() as conn:
        # 获取所有有 embedding 的话题
        query = """
            SELECT t.id, te.embedding
            FROM topics t
            JOIN topic_embeddings te ON t.id = te.topic_id
            WHERE t.agent_id = :agent_id
            AND t.message_count >= :min_count
        """
        params = {"agent_id": agent_id, "min_count": CONFIG["min_messages_for_cluster"]}
        
        if group_id:
            query += " AND t.group_id = :group_id"
            params["group_id"] = group_id
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
    if len(rows) < 2:
        return [[row[0]] for row in rows]
    
    # 构建话题向量列表
    topic_embeddings = []
    for row in rows:
        topic_id, embedding_json = row
        try:
            embedding = json.loads(embedding_json)
            topic_embeddings.append((topic_id, embedding))
        except:
            continue
    
    # 简单聚类：两两比较，相似度高的归为一组
    clusters = []
    assigned = set()
    
    for i, (topic_id_i, emb_i) in enumerate(topic_embeddings):
        if topic_id_i in assigned:
            continue
        
        # 创建新簇
        cluster = [topic_id_i]
        assigned.add(topic_id_i)
        
        for j, (topic_id_j, emb_j) in enumerate(topic_embeddings[i+1:], i+1):
            if topic_id_j in assigned:
                continue
            
            similarity = cosine_similarity(emb_i, emb_j)
            if similarity >= CONFIG["similarity_threshold"]:
                cluster.append(topic_id_j)
                assigned.add(topic_id_j)
        
        clusters.append(cluster)
    
    return clusters


# ==================== 批量处理 ====================

def update_all_topic_embeddings():
    """批量更新所有话题的向量表示"""
    engine = get_db()
    
    with engine.connect() as conn:
        # 获取需要更新向量的话题
        result = conn.execute(text("""
            SELECT t.id, t.name, t.message_count
            FROM topics t
            LEFT JOIN topic_embeddings te ON t.id = te.topic_id
            WHERE te.embedding IS NULL
            AND t.message_count >= :min_count
            ORDER BY t.last_message_at DESC
            LIMIT 50
        """), {"min_count": CONFIG["min_messages_for_cluster"]})
        
        topics = result.fetchall()
    
    print(f"[Vector] Updating embeddings for {len(topics)} topics")
    
    for topic in topics:
        topic_id, name, count = topic
        
        # 获取话题消息
        from api.topic_service import get_topic_messages
        messages = get_topic_messages(topic_id, limit=10)
        
        # 生成向量
        embedding = generate_topic_embedding(topic_id, messages)
        
        if embedding:
            save_topic_embedding(topic_id, embedding)
            print(f"[Vector] Updated embedding for topic: {name} ({count} messages)")
        else:
            print(f"[Vector] Failed to generate embedding for topic: {name}")


if __name__ == "__main__":
    # 测试
    print("[Vector Service] Testing...")
    
    # 测试 embedding
    test_text = "小O，你帮我优化下o-mind的部署问题"
    emb = get_embedding(test_text)
    if emb:
        print(f"Embedding dimension: {len(emb)}")
        print(f"First 5 values: {emb[:5]}")
    
    # 测试相似度
    if emb:
        sim = cosine_similarity(emb[:10], emb[:10])
        print(f"Self similarity: {sim}")
