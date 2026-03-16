/**
 * Memory Server Skill - O-Mind 记忆服务
 * 作为工具供 Agent 调用
 */

const MEMORY_SERVER_URL = process.env.MEMORY_SERVER_URL || 'http://localhost:8000';
const MEMORY_API_KEY = process.env.MEMORY_API_KEY || 'key-prod-1';

/**
 * 调用 O-Mind API
 */
async function callApi(path, method = 'GET', body = null) {
  const url = `${MEMORY_SERVER_URL}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': MEMORY_API_KEY
  };
  
  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);
  
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    throw new Error(`Memory API call failed: ${error.message}`);
  }
}

/**
 * save_memory - 保存记忆
 */
async function save_memory({ content, tags = [], source = 'skill', agent_id = 'openclaw-admin' }) {
  if (!content) {
    throw new Error('content is required');
  }
  
  const result = await callApi('/api/memories', 'POST', {
    content,
    tags,
    source,
    agent_id
  });
  
  return {
    success: true,
    message: `记忆已保存: ${content.slice(0, 50)}...`,
    id: result.id
  };
}

/**
 * search_memories - 搜索记忆
 */
async function search_memories({ query = '', limit = 10, agent_id = '' }) {
  let path = `/api/memories?limit=${limit}`;
  if (query) path += `&q=${encodeURIComponent(query)}`;
  if (agent_id) path += `&agent_id=${encodeURIComponent(agent_id)}`;
  
  const results = await callApi(path);
  
  return {
    success: true,
    count: results.length,
    memories: results.map(m => ({
      id: m.id,
      content: m.content,
      tags: m.tags,
      agent_id: m.agent_id,
      created_at: m.created_at
    }))
  };
}

/**
 * get_memories - 获取所有记忆
 */
async function get_memories({ limit = 50, agent_id = '' }) {
  let path = `/api/memories?limit=${limit}`;
  if (agent_id) path += `&agent_id=${encodeURIComponent(agent_id)}`;
  
  const results = await callApi(path);
  
  return {
    success: true,
    count: results.length,
    memories: results
  };
}

/**
 * get_stats - 获取统计
 */
async function get_stats() {
  const stats = await callApi('/api/stats');
  
  return {
    success: true,
    stats
  };
}

module.exports = {
  save_memory,
  search_memories,
  get_memories,
  get_stats
};
