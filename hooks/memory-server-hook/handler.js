/**
 * Memory Server Hook
 * 自动保存和检索记忆
 */

const MEMORY_SERVER_URL = process.env.MEMORY_SERVER_URL || 'http://memory-server-memory-server-1:8000';

/**
 * HTTP 请求辅助函数
 */
async function callMemoryApi(path, method = 'GET', body = null) {
  const url = `${MEMORY_SERVER_URL}${path}`;
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  try {
    const response = await fetch(url, options);
    return await response.json();
  } catch (error) {
    console.error('Memory API call failed:', error.message);
    return null;
  }
}

/**
 * before_prompt_build hook
 * 每次 LLM 调用前检索相关记忆
 */
export async function before_prompt_build(context) {
  console.log('[memory-hook] before_prompt_build called');
  
  const userMessage = context.userMessage || '';
  if (!userMessage) {
    return { injectedContext: '' };
  }
  
  // 提取关键词搜索
  const keywords = userMessage.slice(0, 100).replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ').trim();
  
  try {
    const memories = await callMemoryApi(`/api/memories?limit=5`);
    if (!memories || memories.length === 0) {
      return { injectedContext: '' };
    }
    
    // 过滤相关记忆
    const relevant = memories.filter(m => 
      m.content.includes(keywords) || 
      keywords.split(' ').some(k => k && m.content.includes(k))
    );
    
    if (relevant.length === 0) {
      return { injectedContext: '' };
    }
    
    const contextText = relevant.map(m => `- ${m.content}`).join('\n');
    return {
      injectedContext: `## 相关记忆\n${contextText}`
    };
  } catch (error) {
    console.error('[memory-hook] Error:', error);
    return { injectedContext: '' };
  }
}

/**
 * before_reset hook
 * /reset 前保存会话摘要
 */
export async function before_reset(context) {
  console.log('[memory-hook] before_reset called');
  
  const summary = context.conversationSummary || '';
  if (!summary) {
    return { allowed: true };
  }
  
  await callMemoryApi('/api/memories', 'POST', {
    content: `会话摘要: ${summary.slice(0, 1000)}`,
    tags: ['session-summary'],
    source: 'hook'
  });
  
  return { allowed: true };
}

/**
 * agent_end hook
 * Agent 完成后保存对话
 */
export async function agent_end(context) {
  console.log('[memory-hook] agent_end called');
  
  const response = context.finalResponse || '';
  if (!response) {
    return;
  }
  
  await callMemoryApi('/api/memories', 'POST', {
    content: response.slice(0, 1000),
    tags: ['agent-response'],
    source: 'hook'
  });
}

export const metadata = {
  name: 'memory-server-hook',
  events: ['prompt:build', 'command:reset', 'agent:end']
};
