/**
 * Memory Server Skill
 * 自建记忆服务 - 替代 mem9 的私有化部署
 * 
 * 实现生命周期钩子：
 * - before_prompt_build: 每次 LLM 调用前注入相关记忆
 * - before_reset: /reset 前保存会话摘要
 * - agent_end: Agent 完成后保存对话
 */

const MEMORY_SERVER_URL = Env("MEMORY_SERVER_URL", "http://memory-server:8000");

export const metadata = {
  name: "memory-server",
  version: "1.0.0",
  description: "自建记忆服务",
  hooks: {
    before_prompt_build: true,
    before_reset: true,
    agent_end: true
  }
};

interface Memory {
  id: string;
  content: string;
  tags: string[];
  source?: string;
  meta: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface StoreOptions {
  content: string;
  tags?: string[];
  source?: string;
  meta?: Record<string, any>;
}

interface SearchOptions {
  query?: string;
  tags?: string[];
  source?: string;
  limit?: number;
  offset?: number;
}

/**
 * 存储记忆
 */
export async function store(options: StoreOptions): Promise<Memory> {
  const response = await fetch(`${MEMORY_SERVER_URL}/api/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options)
  });
  
  if (!response.ok) {
    throw new Error(`memory store failed: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * 搜索记忆
 */
export async function search(options: SearchOptions = {}): Promise<Memory[]> {
  const params = new URLSearchParams();
  if (options.query) params.set("q", options.query);
  if (options.tags?.length) params.set("tags", options.tags.join(","));
  if (options.source) params.set("source", options.source);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));

  const response = await fetch(
    `${MEMORY_SERVER_URL}/api/memories?${params.toString()}`
  );

  if (!response.ok) {
    throw new Error(`memory search failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 获取单条记忆
 */
export async function get(id: string): Promise<Memory> {
  const response = await fetch(`${MEMORY_SERVER_URL}/api/memories/${id}`);
  if (!response.ok) {
    throw new Error(`memory get failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * 更新记忆
 */
export async function update(
  id: string, 
  updates: { content?: string; tags?: string[]; meta?: Record<string, any> }
): Promise<Memory> {
  const response = await fetch(`${MEMORY_SERVER_URL}/api/memories/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates)
  });
  
  if (!response.ok) {
    throw new Error(`memory update failed: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * 删除记忆
 */
export async function remove(id: string): Promise<void> {
  const response = await fetch(`${MEMORY_SERVER_URL}/api/memories/${id}`, {
    method: "DELETE"
  });
  
  if (!response.ok) {
    throw new Error(`memory delete failed: ${response.statusText}`);
  }
}

// ========== 生命周期钩子实现 ==========

/**
 * before_prompt_build 钩子
 * 每次 LLM 调用前自动检索相关记忆并注入上下文
 */
export async function before_prompt_build(context: {
  conversationHistory: string[];
  userMessage: string;
}): Promise<{ injectedContext: string }> {
  // 提取用户消息中的关键词进行搜索
  const keywords = context.userMessage
    .slice(0, 200)
    .replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ')
    .trim()
    .split(/\s+/)
    .slice(0, 5)
    .join(' ');

  if (!keywords) {
    return { injectedContext: '' };
  }

  try {
    const memories = await search({ query: keywords, limit: 3 });
    
    if (memories.length === 0) {
      return { injectedContext: '' };
    }

    const contextText = memories
      .map(m => `- ${m.content}`)
      .join('\n');

    return {
      injectedContext: `## 相关记忆\n${contextText}`
    };
  } catch (e) {
    console.error('before_prompt_build hook error:', e);
    return { injectedContext: '' };
  }
}

/**
 * before_reset 钩子
 * 执行 /reset 前自动保存会话摘要
 */
export async function before_reset(context: {
  conversationSummary: string;
  sessionKey: string;
}): Promise<{ allowed: boolean }> {
  if (!context.conversationSummary) {
    return { allowed: true };
  }

  try {
    await store({
      content: `会话摘要: ${context.conversationSummary}`,
      tags: ['session-summary', context.sessionKey],
      source: 'openclaw'
    });
    console.log('Session summary saved before reset');
  } catch (e) {
    console.error('before_reset hook error:', e);
  }

  return { allowed: true };
}

/**
 * agent_end 钩子
 * Agent 完成后自动保存对话内容
 */
export async function agent_end(context: {
  finalResponse: string;
  sessionKey: string;
  agentId: string;
}): Promise<void> {
  if (!context.finalResponse) {
    return;
  }

  try {
    // 保存最后回复作为记忆
    await store({
      content: context.finalResponse.slice(0, 1000),
      tags: ['agent-response', context.agentId],
      source: context.sessionKey
    });
    console.log('Agent response saved');
  } catch (e) {
    console.error('agent_end hook error:', e);
  }
}
