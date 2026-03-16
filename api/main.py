import os
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Text, JSON, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql

load_dotenv()

app = FastAPI(
    title="O-Mind API", 
    version="2.0.0",
    description="OpenClaw 本地记忆服务 - 支持多实例认证和多Agent隔离"
)

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


@app.post("/api/memories", response_model=MemoryResponse)
async def create_memory(
    memory: MemoryCreate, 
    db=Depends(get_db),
    instance_info: dict = Depends(verify_api_key)
):
    """创建新记忆（自动关联实例和Agent）"""
    memory_id = str(uuid4())
    
    db_memory = MemoryModel(
        id=memory_id,
        content=memory.content,
        tags=memory.tags,
        source=memory.source,
        agent_id=memory.agent_id,
        meta=memory.meta,
        instance_id=instance_info["instance_id"],  # 自动添加实例ID
    )
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
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
    """搜索记忆（自动过滤当前实例）"""
    query = db.query(MemoryModel).filter(
        MemoryModel.instance_id == instance_info["instance_id"]  # 只查询当前实例的记忆
    )

    if source:
        query = query.filter(MemoryModel.source == source)

    if agent_id:
        query = query.filter(MemoryModel.agent_id == agent_id)

    if tags:
        tag_list = tags.split(",")
        for tag in tag_list:
            query = query.filter(MemoryModel.tags.contains(tag))

    if q:
        query = query.filter(MemoryModel.content.contains(q))

    memories = query.offset(offset).limit(limit).all()
    return memories


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

    db_memory.updated_at = datetime.utcnow()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
