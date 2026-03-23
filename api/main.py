import os
from datetime import datetime
# 注意：使用 datetime.now() 获取本地时间
from typing import Optional, List
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Text, JSON, Integer, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Match
import pymysql
import numpy as np

load_dotenv()

app = FastAPI(
    title="O-Mind API", 
    version="2.0.0",
    description="OpenClaw 本地记忆服务 - 支持多实例认证和多Agent隔离"
)

# ============ Qdrant 客户端初始化 ============
def get_qdrant_client():
    qdrant_host = os.getenv("QDRANT_HOST", "memory-qdrant")
    return QdrantClient(host=qdrant_host, port=6333)

# 初始化 Qdrant collection
def init_qdrant_collection():
    """初始化 Qdrant collection（如果不存在）"""
    client = get_qdrant_client()
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if "memories" not in collection_names:
        client.create_collection(
            collection_name="memories",
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        print("[O-Mind] Created Qdrant collection 'memories'")

# 简单的文本 embedding（使用 hash 作为占位符，生产环境应使用 sentence-transformers）
# 初始化 sentence-transformers 模型
EMBEDDING_MODEL = None

def get_embedding_model():
    """获取 embedding 模型（延迟加载）"""
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer
        # 使用轻量级模型
        # 使用国内镜像源下载模型
        import os
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        EMBEDDING_MODEL = SentenceTransformer('BAAI/bge-base-zh-v1.5')
        print("[O-Mind] Loaded bge-base-zh-v1.5 model (768 dim)")
    return EMBEDDING_MODEL

def get_text_embedding(text: str) -> List[float]:
    """将文本转换为向量（使用 sentence-transformers）"""
    try:
        model = get_embedding_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"[O-Mind] Embedding error: {e}")
        # 降级到简单hash
        import hashlib
        h = hashlib.md5(text.encode()).digest()
        vector = list(h * (384 // 16 + 1))[:384]
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

# 判断是否应该保存这条记忆
def should_save_memory(content: str) -> bool:
    """过滤规则：判断是否应该保存这条记忆"""
    if not content:
        return False
    
    # 过滤明显的元数据类内容（完全没用的）
    if content.startswith('Conversation info'):
        return False
    if content.startswith('System:'):
        return False
    if content.startswith('Pre-compaction'):
        return False
    if content.startswith('Sender (untrusted'):
        return False
    
    # 过滤带前缀的元数据
    if content.startswith('- Conversation info'):
        return False
    if content.startswith('- System:'):
        return False
    if content.startswith('- Sender (untrusted'):
        return False
    
    # 过滤太短的（可能无效）
    if len(content) < 3:
        return False
    
    return True

# 保存到 Qdrant
def save_to_qdrant(memory_id: str, content: str, instance_id: str, agent_id: str = None):
    """保存向量到 Qdrant"""
    try:
        client = get_qdrant_client()
        vector = get_text_embedding(content)
        
        client.upsert(
            collection_name="memories",
            points=[
                PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload={
                        "instance_id": instance_id,
                        "agent_id": agent_id or ""
                    }
                )
            ]
        )
        print(f"[O-Mind] Saved vector to Qdrant: {memory_id}")
    except Exception as e:
        print(f"[O-Mind] Qdrant save error: {e}")

# 从 Qdrant 搜索
def search_qdrant(query_text: str, instance_id: str, agent_id: str = None, limit: int = 10) -> List[str]:
    """从 Qdrant 搜索，返回 memory IDs（使用滚动查询+本地过滤）"""
    try:
        client = get_qdrant_client()
        query_vector = get_text_embedding(query_text)
        
        # 获取所有点，然后本地过滤
        all_points, _ = client.scroll(
            collection_name="memories",
            limit=100,
            with_vectors=True
        )
        
        # 计算相似度并过滤
        results = []
        for point in all_points:
            payload = point.payload or {}
            if payload.get("instance_id") != instance_id:
                continue
            if agent_id and payload.get("agent_id") != agent_id:
                continue
            
            # 计算余弦相似度
            if point.vector and isinstance(point.vector, list):
                dot = sum(a * b for a, b in zip(query_vector, point.vector))
                norm1 = sum(a * a for a in query_vector) ** 0.5
                norm2 = sum(a * a for a in point.vector) ** 0.5
                if norm1 > 0 and norm2 > 0:
                    score = dot / (norm1 * norm2)
                    # 只返回相似度 >= threshold 的结果
                    threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
                    if score >= threshold:
                        results.append((point.id, score))
        
        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [r[0] for r in results[:limit]]
    except Exception as e:
        print(f"[O-Mind] Qdrant search error: {e}")
        return []

# 启动时初始化
init_qdrant_collection()

# 启动定时摘要任务
def start_summary_scheduler():
    """启动每小时摘要定时任务"""
    import threading
    import time
    from datetime import datetime
    
    def run_summary():
        while True:
            # 每小时运行一次
            time.sleep(3600)
            try:
                from api.summary_task import run_hourly_summary
                print(f"[Scheduler] Running hourly summary at {datetime.now()}")
                run_summary()
            except Exception as e:
                print(f"[Scheduler] Summary task failed: {e}")
    
    thread = threading.Thread(target=run_summary, daemon=True)
    thread.start()
    print("[Scheduler] Hourly summary scheduler started")


def start_topic_scheduler():
    """启动话题定时任务"""
    import threading
    import time
    from datetime import datetime
    
    def run_topic_summary():
        while True:
            # 每30分钟运行一次
            time.sleep(1800)
            try:
                from api.topic_scheduler import run_topic_scheduler
                print(f"[Topic Scheduler] Running at {datetime.now()}")
                run_topic_scheduler()
            except Exception as e:
                print(f"[Topic Scheduler] Topic task failed: {e}")
    
    thread = threading.Thread(target=run_topic_summary, daemon=True)
    thread.start()
    print("[Topic Scheduler] Topic scheduler started")

# 启动定时摘要任务
start_summary_scheduler()
start_topic_scheduler()

# ============ 多实例认证支持 ============

# API Key 存储 (生产环境应该用数据库)
# 格式: "key": {"instance_id": "xxx", "name": "xxx"}
API_KEYS = {
    "key-prod-1": {"instance_id": "prod-1", "name": "prod1"},
    "key-test-1": {"instance_id": "test-1", "name": "test1"},
    "key-dev-local": {"instance_id": "dev-local", "name": "dev1"},
}

# 从环境变量加载额外的 API Keys
def load_api_keys():
    """从环境变量加载额外的 API Keys"""
    import json
    keys_json = os.getenv("MEMORY_API_KEYS", "{}")
    if keys_json:
        try:
            # 尝试修复 JSON 格式
            import re
            # 添加缺失的引号
            fixed = re.sub(r'([{,])(\w+):', r'\1"\2":', keys_json)
            keys = json.loads(fixed)
            API_KEYS.update(keys)
            print(f"[O-Mind] Loaded {len(API_KEYS)} API keys total")
        except Exception as e:
            print(f"[O-Mind] Failed to load API keys from env: {e}")

load_api_keys()


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """验证 API Key 并返回实例信息"""
    if not x_api_key:
        # 如果没有 API Key，使用默认实例（兼容旧版本）
        return {"instance_id": "default", "name": "default"}
    
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    return API_KEYS[x_api_key]


def get_current_instance():
    """获取当前实例的认证信息"""
    return Depends(verify_api_key)


# ============ 数据库模型 ============

Base = declarative_base()


class MemoryModel(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    source = Column(String(255), nullable=True)
    instance_id = Column(String(64), nullable=False, default="default")  # 实例ID
    agent_id = Column(String(64), nullable=True)  # Agent ID
    meta = Column(JSON, default=dict)
    vector_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    topic_id = Column(String(36), nullable=True)
    topic_type = Column(String(20), nullable=True)
    is_topic_summary = Column(String(10), nullable=True)


class TopicModel(Base):
    __tablename__ = "topics"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=True)
    topic_type = Column(String(20), default="session")
    status = Column(String(20), default="active")
    session_id = Column(String(36), nullable=True)
    parent_topic_id = Column(String(36), nullable=True)
    message_count = Column(Integer, default=0)
    user_message_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    summary_version = Column(Integer, default=1)
    keywords = Column(JSON, nullable=True)
    context_embedding = Column(JSON, nullable=True)
    agent_id = Column(String(255), nullable=True)
    group_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TopicMessageModel(Base):
    __tablename__ = "topic_messages"
    
    id = Column(String(36), primary_key=True)
    topic_id = Column(String(36), nullable=False)
    memory_id = Column(String(36), nullable=False)
    role = Column(String(20), nullable=True)
    sequence_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# ============ Pydantic 模型 ============

class MemoryCreate(BaseModel):
    content: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    agent_id: Optional[str] = None  # 可选的 Agent ID
    meta: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    agent_id: Optional[str] = None
    meta: Optional[dict] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    tags: List[str]
    source: Optional[str]
    instance_id: str
    agent_id: Optional[str]
    meta: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 数据库连接 ============

def get_db():
    mysql_host = os.getenv("MYSQL_HOST", "memory-mysql")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "123456")
    mysql_database = os.getenv("MYSQL_DATABASE", "memory")

    # 创建数据库
    conn = pymysql.connect(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        password=mysql_password
    )
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_database}")
    conn.close()

    mysql_url = (
        f"mysql+pymysql://{mysql_user}:{mysql_password}@"
        f"{mysql_host}:{mysql_port}/"
        f"{mysql_database}"
    )
    engine = create_engine(mysql_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ============ 路由 ============

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "O-Mind", "version": "2.0.0"}


@app.get("/api/keys/verify")
async def verify_key(x_api_key: Optional[str] = Header(None)):
    """验证 API Key"""
    if not x_api_key:
        return {"valid": False, "message": "No API Key provided"}
    
    if x_api_key in API_KEYS:
        return {"valid": True, "instance": API_KEYS[x_api_key]}
    
    return {"valid": False, "message": "Invalid API Key"}


@app.post("/api/memories")
async def create_memory(
    memory: MemoryCreate, 
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """创建新记忆（自动关联实例和Agent）- 混合模式：MySQL + Qdrant"""
    
    content = memory.content.strip() if memory.content else ""
    if not content:
        return {"status": "error", "message": "Empty content"}
    
    instance_id = instance_info["instance_id"]
    
    # 检查是否已存在相同的记忆（去重）
    existing = db.query(MemoryModel).filter(
        MemoryModel.content == content,
        MemoryModel.instance_id == instance_id
    ).first()
    
    if existing:
        return {"status": "duplicate", "id": existing.id, "message": "Memory already exists"}
    
    memory_id = str(uuid4())
    
    # 1. 保存到 MySQL
    db_memory = MemoryModel(
        id=memory_id,
        content=content,
        tags=memory.tags,
        source=memory.source,
        agent_id=memory.agent_id,
        meta=memory.meta,
        instance_id=instance_id,
    )
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    
    # 2. 同时保存到 Qdrant（向量数据库）
    save_to_qdrant(memory_id, content, instance_id, memory.agent_id)
    
    # 3. 话题识别与关联
    try:
        from api.topic_service import process_message
        # 判断是否是用户消息
        role = "user" if memory.source in ["hook", "user"] else "assistant"
        topic_id = process_message(memory.agent_id, content, memory_id, role)
        print(f"[O-Mind] Message linked to topic: {topic_id}")
    except Exception as e:
        print(f"[O-Mind] Topic processing error: {e}")
    
    return db_memory
    
    memory_id = str(uuid4())
    instance_id = instance_info["instance_id"]
    
    # 1. 保存到 MySQL
    db_memory = MemoryModel(
        id=memory_id,
        content=content,
        tags=memory.tags,
        source=memory.source,
        agent_id=memory.agent_id,
        meta=memory.meta,
        instance_id=instance_id,
    )
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    
    # 2. 同时保存到 Qdrant（向量数据库）
    save_to_qdrant(memory_id, memory.content, instance_id, memory.agent_id)
    
    return db_memory


@app.get("/api/memories", response_model=List[MemoryResponse])
async def search_memories(
    q: Optional[str] = None,
    tags: Optional[str] = None,
    source: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """搜索记忆 - 混合模式：Qdrant 向量搜索 + MySQL 查询"""
    instance_id = instance_info["instance_id"]
    
    # 如果有查询文本，使用 Qdrant 向量搜索
    if q:
        # 1. 从 Qdrant 获取匹配的 ID 列表
        memory_ids = search_qdrant(q, instance_id, agent_id, limit)
        
        if memory_ids:
            # 2. 从 MySQL 查询完整记录
            memories = db.query(MemoryModel).filter(
                MemoryModel.id.in_(memory_ids),
                MemoryModel.instance_id == instance_id
            ).all()
            
            # 保持 Qdrant 返回的顺序
            id_to_memory = {m.id: m for m in memories}
            results = [id_to_memory[mid] for mid in memory_ids if mid in id_to_memory]
        else:
            results = []
    else:
        results = []
    
    # 自动获取最新摘要并添加到结果最前面（按 agent 维度）
    summary = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_id,
        MemoryModel.agent_id == agent_id,  # 只获取当前 agent 的摘要
        MemoryModel.tags.like('%summary%')
    ).order_by(MemoryModel.created_at.desc()).first()
    
    if summary:
        # 将摘要放到结果最前面（如果不在结果中）
        if summary not in results:
            results.insert(0, summary)
        # 如果摘要已在结果中（通过向量搜索匹配），移到最前
        elif results[0] != summary:
            results.remove(summary)
            results.insert(0, summary)
    
    return results
    
    # 无查询文本时，使用 MySQL 普通查询
    query = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_id
    )

    if source:
        query = query.filter(MemoryModel.source == source)

    if agent_id:
        query = query.filter(MemoryModel.agent_id == agent_id)

    if tags:
        tag_list = tags.split(",")
        for tag in tag_list:
            query = query.filter(MemoryModel.tags.contains(tag))

    # 按创建时间倒序排列
    memories = query.order_by(MemoryModel.created_at.desc()).offset(offset).limit(limit).all()
    return memories


@app.get("/api/memories/list")
async def list_memories(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    tags: Optional[str] = None,
    source: Optional[str] = None,
    agent_id: Optional[str] = None,
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """分页获取记忆列表（专门给前端用）"""
    instance_id = instance_info["instance_id"]
    
    # 构建查询
    query = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_id
    )
    
    # 关键词搜索（使用 LIKE）
    if q:
        query = query.filter(MemoryModel.content.contains(q))
    
    if source:
        query = query.filter(MemoryModel.source == source)
    
    if agent_id:
        query = query.filter(MemoryModel.agent_id == agent_id)
    
    if tags:
        tag_list = tags.split(",")
        for tag in tag_list:
            query = query.filter(MemoryModel.tags.contains(tag))
    
    # 获取总数
    total = query.count()
    
    # 分页查询
    offset = (page - 1) * page_size
    memories = query.order_by(MemoryModel.created_at.desc()).offset(offset).limit(page_size).all()
    
    # 自动获取最新摘要并添加到结果最前面（首页且无搜索时）
    if page == 1 and not q:
        summary = db.query(MemoryModel).filter(
            MemoryModel.instance_id == instance_id,
            MemoryModel.tags.like('%summary%')
        ).order_by(MemoryModel.created_at.desc()).first()
        
        if summary and summary not in memories:
            memories.insert(0, summary)
    
    return {
        "items": memories,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
    
    return {
        "items": memories,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@app.get("/api/memories/search/vector", response_model=List[MemoryResponse])
async def vector_search(
    query_text: str,
    limit: int = 10,
    agent_id: Optional[str] = None,
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """向量搜索记忆（自动过滤当前实例）"""
    # 简化实现：使用关键词匹配
    query = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    )
    
    if agent_id:
        query = query.filter(MemoryModel.agent_id == agent_id)
    
    # 简单关键词匹配（生产环境应使用 Qdrant 向量搜索）
    memories = query.filter(
        MemoryModel.content.contains(query_text)
    ).limit(limit).all()
    
    return memories


@app.get("/api/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str, 
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """获取单条记忆（验证所有权）"""
    memory = db.query(MemoryModel).filter(
        and_(
            MemoryModel.id == memory_id,
            MemoryModel.instance_id == instance_info["instance_id"]
        )
    ).first()
    
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@app.put("/api/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str, 
    memory: MemoryUpdate, 
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """更新记忆（验证所有权）"""
    db_memory = db.query(MemoryModel).filter(
        and_(
            MemoryModel.id == memory_id,
            MemoryModel.instance_id == instance_info["instance_id"]
        )
    ).first()
    
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if memory.content is not None:
        db_memory.content = memory.content
    if memory.tags is not None:
        db_memory.tags = memory.tags
    if memory.agent_id is not None:
        db_memory.agent_id = memory.agent_id
    if memory.meta is not None:
        db_memory.meta = memory.meta

    db_memory.updated_at = datetime.now()
    db.commit()
    db.refresh(db_memory)
    return db_memory


@app.delete("/api/memories/{memory_id}")
async def delete_memory(
    memory_id: str, 
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """删除记忆（验证所有权）"""
    db_memory = db.query(MemoryModel).filter(
        and_(
            MemoryModel.id == memory_id,
            MemoryModel.instance_id == instance_info["instance_id"]
        )
    ).first()
    
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    db.delete(db_memory)
    db.commit()
    return {"status": "deleted", "id": memory_id}


@app.get("/api/instances/info")
async def get_instance_info(instance_info: dict = Depends(verify_api_key)):
    """获取当前实例信息"""
    return instance_info


@app.get("/api/agents")
async def list_agents(
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """列出当前实例的所有Agent"""
    agents = db.query(MemoryModel.agent_id).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    ).distinct().all()
    
    return [a[0] for a in agents if a[0]]


@app.post("/api/memories/batch-delete")
async def batch_delete_memories(
    ids: List[str],
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """批量删除记忆"""
    deleted_count = 0
    for memory_id in ids:
        db_memory = db.query(MemoryModel).filter(
            and_(
                MemoryModel.id == memory_id,
                MemoryModel.instance_id == instance_info["instance_id"]
            )
        ).first()
        if db_memory:
            db.delete(db_memory)
            deleted_count += 1
    
    db.commit()
    return {"status": "deleted", "count": deleted_count}


@app.get("/api/memories/export")
async def export_memories(
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """导出所有记忆为 JSON"""
    memories = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    ).all()
    
    return [{
        "id": m.id,
        "content": m.content,
        "tags": m.tags,
        "source": m.source,
        "agent_id": m.agent_id,
        "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None
    } for m in memories]


@app.post("/api/memories/import")
async def import_memories(
    memories: List[dict],
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """批量导入记忆"""
    imported_count = 0
    for mem_data in memories:
        memory_id = mem_data.get("id", str(uuid4()))
        db_memory = MemoryModel(
            id=memory_id,
            content=mem_data.get("content", ""),
            tags=mem_data.get("tags", []),
            source=mem_data.get("source", "import"),
            agent_id=mem_data.get("agent_id"),
            meta=mem_data.get("meta", {}),
            instance_id=instance_info["instance_id"],
        )
        db.add(db_memory)
        imported_count += 1
    
    db.commit()
    return {"status": "imported", "count": imported_count}


@app.get("/api/stats")
async def get_stats(
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """获取统计信息"""
    total = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    ).count()
    
    agents = db.query(MemoryModel.agent_id).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    ).distinct().all()
    
    # 按标签统计
    all_memories = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_info["instance_id"]
    ).all()
    
    tag_counts = {}
    for m in all_memories:
        if m.tags:
            for tag in m.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    return {
        "total_memories": total,
        "total_agents": len([a[0] for a in agents if a[0]]),
        "tag_counts": tag_counts,
        "instance_id": instance_info["instance_id"]
    }


# ============ 话题 API ============

@app.get("/api/topics")
async def list_topics(
    agent_id: Optional[str] = None,
    status: str = "active",
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """获取话题列表"""
    query = db.query(TopicModel).filter(
        TopicModel.agent_id == agent_id
    ) if agent_id else db.query(TopicModel)
    
    if status:
        query = query.filter(TopicModel.status == status)
    
    total = query.count()
    topics = query.order_by(TopicModel.last_message_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "topic_type": t.topic_type,
                "status": t.status,
                "message_count": t.message_count,
                "summary": t.summary[:200] + "..." if t.summary and len(t.summary) > 200 else t.summary,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
            }
            for t in topics
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@app.get("/api/topics/{topic_id}")
async def get_topic(
    topic_id: str,
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """获取话题详情"""
    topic = db.query(TopicModel).filter(TopicModel.id == topic_id).first()
    
    if not topic:
        return {"error": "Topic not found"}
    
    # 获取话题消息
    topic_msgs = db.query(TopicMessageModel).filter(
        TopicMessageModel.topic_id == topic_id
    ).order_by(TopicMessageModel.sequence_order).all()
    
    memories = []
    for tm in topic_msgs:
        mem = db.query(MemoryModel).filter(MemoryModel.id == tm.memory_id).first()
        if mem:
            memories.append({
                "id": mem.id,
                "content": mem.content[:200] + "..." if len(mem.content) > 200 else mem.content,
                "role": tm.role,
                "created_at": mem.created_at.isoformat() if mem.created_at else None
            })
    
    return {
        "id": topic.id,
        "name": topic.name,
        "topic_type": topic.topic_type,
        "status": topic.status,
        "message_count": topic.message_count,
        "summary": topic.summary,
        "started_at": topic.started_at.isoformat() if topic.started_at else None,
        "last_message_at": topic.last_message_at.isoformat() if topic.last_message_at else None,
        "messages": memories
    }


@app.get("/api/topics/{topic_id}/relations")
async def get_topic_relations(topic_id: str):
    """获取话题的关联话题"""
    from sqlalchemy import text
    
    relations = db.execute(text("""
        SELECT tr.target_topic_id, tr.similarity, t.name, t.topic_type, t.status, t.last_message_at
        FROM topic_relations tr
        JOIN topics t ON tr.target_topic_id = t.id
        WHERE tr.source_topic_id = :topic_id
        ORDER BY tr.similarity DESC
        LIMIT 10
    """), {"topic_id": topic_id}).fetchall()
    
    return {
        "topic_id": topic_id,
        "relations": [
            {
                "topic_id": r[0],
                "similarity": r[1],
                "name": r[2],
                "topic_type": r[3],
                "status": r[4],
                "last_message_at": r[5].isoformat() if r[5] else None
            }
            for r in relations
        ]
    }


@app.get("/api/topics/{topic_id}/tree")
async def get_topic_tree(topic_id: str):
    """获取话题的树结构（父话题 + 子话题）"""
    try:
        from api.topic_service import get_topic_tree
        return get_topic_tree(topic_id)
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/topics/{topic_id}/aggregate")
async def aggregate_subtopic_summaries(topic_id: str):
    """聚合子话题摘要到父话题"""
    try:
        from api.topic_service import aggregate_subtopic_summaries, save_topic_summary
        summary = aggregate_subtopic_summaries(topic_id)
        if summary:
            save_topic_summary(topic_id, summary)
            return {"status": "success", "summary": summary}
        return {"status": "no_subtopics", "message": "No subtopic summaries to aggregate"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/topics/batch-update-embeddings")
async def batch_update_embeddings():
    """批量更新话题向量"""
    try:
        from api.vector_service import update_all_topic_embeddings
        update_all_topic_embeddings()
        return {"status": "success", "message": "Topic embeddings updated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
