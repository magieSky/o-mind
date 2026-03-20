#!/usr/bin/env python3
"""
导入 OpenClaw 会话历史到 o-mind
用法: python import_sessions.py [--agents-dir PATH] [--api-url URL] [--api-key KEY]
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# 设置 UTF-8 编码
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 设置控制台输出编码
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 默认配置
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_API_KEY = "key-prod-1"
DEFAULT_AGENTS_DIR = r"C:\Users\36153\.openclaw\agents"

# 需要过滤的元数据前缀
METADATA_PREFIXES = [
    "Conversation info",
    "Sender (untrusted",
    "[System:",
    "Pre-compaction memory",
    "HEARTBEAT_OK",
]

def clean_content(content: str) -> str:
    """清理消息内容，去除元数据"""
    content = content.strip()
    
    # 如果是 JSON 格式，尝试解析并提取 text 字段
    if content.startswith("json") or content.startswith("{"):
        try:
            # 尝试解析 JSON
            if content.startswith("json"):
                content = content[4:].strip()
            data = json.loads(content)
            
            # 如果是对象，尝试找 text 字段
            if isinstance(data, dict):
                if "text" in data:
                    content = data["text"]
                else:
                    # 有其他字段但没有 text，说明是元数据
                    return ""
        except (json.JSONDecodeError, ValueError):
            pass
    
    # 检查是否包含元数据关键字（说明是元数据）
    metadata_indicators = [
        "message_id", "sender_id", "conversation_label",
        "sender", "timestamp", "group_subject", "was_mentioned"
    ]
    indicator_count = sum(1 for ind in metadata_indicators if ind in content)
    if indicator_count >= 3:
        return ""  # 太像元数据了
    
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 跳过元数据行
        is_metadata = False
        for prefix in METADATA_PREFIXES:
            if line.startswith(prefix):
                is_metadata = True
                break
        
        if is_metadata:
            continue
            
        # 跳过 message_id 行
        if "[message_id:" in line:
            continue
            
        if line.strip():
            cleaned_lines.append(line)
    
    result = '\n'.join(cleaned_lines).strip()
    
    # 过滤太短的内容
    if len(result) < 5:
        return ""
    
    # 过滤噪音消息
    noise_patterns = [
        "NO_REPLY",
        "Current time:",
        "Agent-to-agent announcement",
        "Pre-compaction memory",
        "HEARTBEAT_OK",
    ]
    for pattern in noise_patterns:
        if result.startswith(pattern):
            return ""
    
    return result

def extract_user_messages(line: dict) -> list:
    """从会话行中提取用户和助手消息"""
    messages = []
    
    if line.get("type") != "message":
        return messages
        
    msg = line.get("message", {})
    role = msg.get("role")
    
    # 同时提取 user 和 assistant 的消息
    if role not in ["user", "assistant"]:
        return messages
    
    content = msg.get("content", [])
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image":
                    # 图片用 URL 或 描述代替
                    text_parts.append(f"[图片: {part.get('source', 'unknown')}]")
        content = "".join(text_parts)
    elif not isinstance(content, str):
        content = str(content)
    
    # 预先过滤噪音消息 - 检查整个内容
    content_lower = content.lower()
    noise_keywords = [
        "no_reply",
        "current time:",
        "agent-to-agent announcement",
        "pre-compaction memory",
        "heartbeat_ok",
    ]
    for keyword in noise_keywords:
        if keyword in content_lower:
            return []
    
    # 清理内容
    cleaned = clean_content(content)
    
    # 过滤太短的内容
    if len(cleaned) < 3:
        return messages
    
    return [{"content": cleaned, "timestamp": line.get("timestamp", ""), "role": role}]

def parse_session_file(filepath: Path, agent_id: str) -> list:
    """解析单个会话文件"""
    memories = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msgs = extract_user_messages(data)
                    for msg in msgs:
                        role_tag = msg.get("role", "user")
                        memories.append({
                            "content": msg["content"],
                            "agent_id": agent_id,
                            "tags": ["import", "history", role_tag],
                            "source": f"import:{filepath.name}"
                        })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    
    return memories

def import_memories(memories: list, api_url: str, api_key: str) -> dict:
    """批量导入记忆到 o-mind"""
    if not memories:
        return {"imported": 0, "failed": 0}
    
    # 分批导入，每批 50 条
    batch_size = 50
    imported = 0
    failed = 0
    
    for i in range(0, len(memories), batch_size):
        batch = memories[i:i+batch_size]
        
        # 逐条导入（API 只支持单条）
        for memory in batch:
            try:
                data = json.dumps(memory).encode('utf-8')
                req = urllib.request.Request(
                    f"{api_url}/api/memories",
                    data=data,
                    headers={
                        'X-API-Key': api_key,
                        'Content-Type': 'application/json'
                    }
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
                    imported += 1
            except Exception as e:
                print(f"    Failed to import: {e}")
                failed += 1
        
        print(f"  Progress: {i+len(batch)}/{len(memories)}")
    
    return {"imported": imported, "failed": failed}

def main():
    parser = argparse.ArgumentParser(description="Import OpenClaw sessions to o-mind")
    parser.add_argument("--agents-dir", default=DEFAULT_AGENTS_DIR, help="Agents directory")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="o-mind API URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="o-mind API Key")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without importing")
    
    args = parser.parse_args()
    
    agents_dir = Path(args.agents_dir)
    if not agents_dir.exists():
        print(f"Error: Agents directory not found: {agents_dir}")
        return
    
    print(f"Scanning: {agents_dir}")
    print(f"API: {args.api_url}")
    print()
    
    total_memories = 0
    total_files = 0
    
    # 遍历所有 agents
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        
        agent_id = agent_dir.name
        sessions_dir = agent_dir / "sessions"
        
        if not sessions_dir.exists():
            continue
        
        # 查找所有 jsonl 文件（排除 lock 和 reset 文件）
        session_files = list(sessions_dir.glob("*.jsonl"))
        
        # 过滤掉 lock 和 reset 文件
        session_files = [f for f in session_files if ".lock" not in f.name and ".reset" not in f.name]
        
        if not session_files:
            continue
        
        print(f"Agent: {agent_id} ({len(session_files)} sessions)")
        
        # 解析所有会话文件
        memories = []
        for session_file in session_files:
            msgs = parse_session_file(session_file, agent_id)
            memories.extend(msgs)
        
        if memories:
            print(f"  Found {len(memories)} user messages")
            
            if args.dry_run:
                # 只显示前3条
                for m in memories[:3]:
                    preview = m['content'][:50].replace('\n', ' ')
                    print(f"    - {preview}...")
            else:
                # 导入到 o-mind
                result = import_memories(memories, args.api_url, args.api_key)
                print(f"  Imported: {result['imported']}, Failed: {result['failed']}")
            
            total_memories += len(memories)
        total_files += len(session_files)
    
    print()
    print(f"Total: {total_files} sessions, {total_memories} messages")
    
    if args.dry_run:
        print("\nThis was a dry run. Run without --dry-run to import.")

if __name__ == "__main__":
    main()
