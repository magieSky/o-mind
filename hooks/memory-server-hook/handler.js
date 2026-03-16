/**
 * O-Mind Hook - 多实例认证版本
 * 支持 API Key 认证和多 Agent 隔离
 * 包含快速失败机制
 */

const MEMORY_SERVER_URL = process.env.MEMORY_SERVER_URL || 'http://memory-server-memory-server-1:8000';
const API_KEY = process.env.MEMORY_API_KEY || '';
const TIMEOUT_MS = 3000; // 3秒超时

/**
 * 带超时的 fetch 封装
 */
async function fetchWithTimeout(url, options = {}, timeout = TIMEOUT_MS) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    if (error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  }
}

/**
 * HTTP 请求辅助函数 - 带认证和快速失败
 */
async function callMemoryApi(path, method = 'GET', body = null) {
  const url = `${MEMORY_SERVER_URL}${path}`;
  const headers = { 'Content-Type': 'application/json' };
  
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  
  const options = {
    method,
    headers
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  try {
    const response = await fetchWithTimeout(url, options, TIMEOUT_MS);
    if (!response.ok) {
      console.error(`[O-Mind] API error: ${response.status} ${response.statusText}`);
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('[O-Mind] API call failed:', error.message);
    return null;
  }
}

/**
 * before_prompt_build hook
 * 每次 LLM 调用前检索相关记忆
 */
export async function before_prompt_build(context) {
  console.log('[O-Mind] before_prompt_build called');
  
  const userMessage = context.userMessage || '';
  if (!userMessage) {
    return { injectedContext: '' };
  }
  
  const keywords = userMessage.slice(0, 100).replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ').trim();
  
  if (!keywords) {
    return { injectedContext: '' };
  }
  
  try {
    const memories = await callMemoryApi(`/api/memories?q=${encodeURIComponent(keywords)}&limit=5`);
    
    if (!memories || memories.length === 0) {
      return { injectedContext: '' };
    }
    
    const contextText = memories.map(m => `- ${m.content}`).join('\n');
    
    return {
      injectedContext: `## 相关记忆\n${contextText}`
    };
  } catch (error) {
    console.error('[O-Mind] Error:', error);
    return { injectedContext: '' };
  }
}

/**
 * before_reset hook
 */
export async function before_reset(context) {
  console.log('[O-Mind] before_reset called');
  
  const summary = context.conversationSummary || '';
  if (!summary) {
    return { allowed: true };
  }
  
  try {
    await callMemoryApi('/api/memories', 'POST', {
      content: `会话摘要: ${summary.slice(0, 1000)}`,
      tags: ['session-summary'],
      source: 'hook',
      agent_id: context.agentId || 'unknown'
    });
  } catch (error) {
    console.error('[O-Mind] before_reset error:', error);
  }
  
  return { allowed: true };
}

/**
 * agent_end hook
 */
export async function agent_end(context) {
  console.log('[O-Mind] agent_end called');
  
  const response = context.finalResponse || '';
  if (!response) {
    return;
  }
  
  try {
    await callMemoryApi('/api/memories', 'POST', {
      content: response.slice(0, 1000),
      tags: ['agent-response'],
      source: 'hook',
      agent_id: context.agentId || 'unknown'
    });
  } catch (error) {
    console.error('[O-Mind] agent_end error:', error);
  }
}

export const metadata = {
  name: 'o-mind-hook',
  events: ['prompt:build', 'command:reset', 'agent:end'],
  description: 'O-Mind 多实例记忆服务 Hook (带快速失败)'
};
