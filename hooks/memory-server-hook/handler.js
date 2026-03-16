/**
 * O-Mind Hook - 多实例认证版本
 * 支持 API Key 认证和多 Agent 隔离
 */

const MEMORY_SERVER_URL = process.env.MEMORY_SERVER_URL || 'http://memory-server-memory-server-1:8000';
const API_KEY = process.env.MEMORY_API_KEY || '';  // 实例 API Key

/**
 * HTTP 请求辅助函数 - 带认证
 */
async function callMemoryApi(path, method = 'GET', body = null) {
  const url = `${MEMORY_SERVER_URL}${path}`;
  const headers = { 'Content-Type': 'application/json' };
  
  // 添加 API Key 认证
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
    const response = await fetch(url, options);
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
 * 每次 LLM 调用前检索相关记忆（自动过滤当前实例和Agent）
 */
export async function before_prompt_build(context) {
  console.log('[O-Mind] before_prompt_build called');
  console.log('[O-Mind] Instance:', API_KEY ? 'authenticated' : 'default');
  
  const userMessage = context.userMessage || '';
  if (!userMessage) {
    return { injectedContext: '' };
  }
  
  // 提取关键词搜索
  const keywords = userMessage.slice(0, 100).replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ').trim();
  
  if (!keywords) {
    return { injectedContext: '' };
  }
  
  try {
    // 搜索当前实例的记忆
    const memories = await callMemoryApi(`/api/memories?q=${encodeURIComponent(keywords)}&limit=5`);
    
    if (!memories || memories.length === 0) {
      return { injectedContext: '' };
    }
    
    // 格式化记忆
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
 * /reset 前保存会话摘要
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
    console.log('[O-Mind] Session summary saved');
  } catch (error) {
    console.error('[O-Mind] before_reset error:', error);
  }
  
  return { allowed: true };
}

/**
 * agent_end hook
 * Agent 完成后保存对话
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
    console.log('[O-Mind] Agent response saved');
  } catch (error) {
    console.error('[O-Mind] agent_end error:', error);
  }
}

/**
 * 获取当前实例信息
 */
export async function get_instance_info() {
  return await callMemoryApi('/api/instances/info');
}

/**
 * 列出当前实例的所有 Agent
 */
export async function list_agents() {
  return await callMemoryApi('/api/agents');
}

export const metadata = {
  name: 'o-mind-hook',
  events: ['prompt:build', 'command:reset', 'agent:end'],
  description: 'O-Mind 多实例记忆服务 Hook'
};
