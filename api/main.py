import os
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql

load_dotenv()

app = FastAPI(title="Memory Server", version="1.0.0")

# Database models
Base = declarative_base()


class MemoryModel(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list)
    source = Column(String(255), nullable=True)
    meta = Column(JSON, default=dict)
    vector_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic models
class MemoryCreate(BaseModel):
    content: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    meta: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    meta: Optional[dict] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    tags: List[str]
    source: Optional[str]
    meta: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Qdrant client
def get_qdrant_client():
    try:
        from qdrant_client import QdrantClient
        qdrant_host = os.getenv("QDRANT_HOST", "memory-qdrant")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        return QdrantClient(host=qdrant_host, port=qdrant_port)
    except Exception as e:
        print(f"Qdrant connection error: {e}")
        return None


# Ensure Qdrant collection exists
def init_qdrant():
    client = get_qdrant_client()
    if client:
        try:
            from qdrant_client.models import Distance, VectorParams
            client.recreate_collection(
                collection_name="memories",
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print("Qdrant collection 'memories' ready")
        except Exception as e:
            print(f"Qdrant init error: {e}")


# Initialize Qdrant on startup
init_qdrant()


# Database setup
def get_db():
    mysql_host = os.getenv("MYSQL_HOST", "memory-mysql")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "123456")
    mysql_database = os.getenv("MYSQL_DATABASE", "memory")

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "memory-server"}


@app.post("/api/memories", response_model=MemoryResponse)
async def create_memory(memory: MemoryCreate, db=Depends(get_db)):
    """创建新记忆"""
    memory_id = str(uuid4())
    db_memory = MemoryModel(
        id=memory_id,
        content=memory.content,
        tags=memory.tags,
        source=memory.source,
        meta=memory.meta,
    )
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    
    # Store vector in Qdrant
    client = get_qdrant_client()
    if client:
        try:
            from qdrant_client.models import PointStruct
            # Simple hash-based vector (for demo, in production use proper embedding)
            import hashlib
            vector = [float(b) / 255.0 for b in hashlib.md5(memory.content.encode()).digest()[:48]]
            vector.extend([0.0] * (384 - len(vector)))
            
            client.upsert(
                collection_name="memories",
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload={
                            "content": memory.content,
                            "tags": memory.tags,
                            "source": memory.source
                        }
                    )
                ]
            )
        except Exception as e:
            print(f"Qdrant upsert error: {e}")
    
    return db_memory


@app.get("/api/memories", response_model=List[MemoryResponse])
async def search_memories(
    q: Optional[str] = None,
    tags: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    db=Depends(get_db)
):
    """搜索记忆"""
    query = db.query(MemoryModel)

    if source:
        query = query.filter(MemoryModel.source == source)

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
    db=Depends(get_db)
):
    """向量搜索记忆"""
    client = get_qdrant_client()
    if not client:
        raise HTTPException(status_code=503, detail="Vector search unavailable")
    
    try:
        import hashlib
        vector = [float(b) / 255.0 for b in hashlib.md5(query_text.encode()).digest()[:48]]
        vector.extend([0.0] * (384 - len(vector)))
        
        results = client.search(
            collection_name="memories",
            query_vector=vector,
            limit=limit
        )
        
        # Get memories by IDs
        memory_ids = [r.id for r in results]
        memories = db.query(MemoryModel).filter(MemoryModel.id.in_(memory_ids)).all()
        return memories
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get("/api/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str, db=Depends(get_db)):
    """获取单条记忆"""
    memory = db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@app.put("/api/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: str, memory: MemoryUpdate, db=Depends(get_db)):
    """更新记忆"""
    db_memory = db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if memory.content is not None:
        db_memory.content = memory.content
    if memory.tags is not None:
        db_memory.tags = memory.tags
    if memory.meta is not None:
        db_memory.meta = memory.meta

    db_memory.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_memory)
    return db_memory


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str, db=Depends(get_db)):
    """删除记忆"""
    db_memory = db.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    db.delete(db_memory)
    db.commit()
    
    # Delete from Qdrant
    client = get_qdrant_client()
    if client:
        try:
            client.delete(
                collection_name="memories",
                points_selector=[memory_id]
            )
        except:
            pass
    
    return {"status": "deleted", "id": memory_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
