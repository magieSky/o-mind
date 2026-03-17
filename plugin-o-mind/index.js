/**
 * O-Mind Plugin
 * 私有化部署的本地记忆服务
 */

const PLUGIN_ID = 'o-mind';

// 获取配置
function getMemoryUrl(ctx) {
  return ctx?.config?.memoryServerUrl || process.env.MEMORY_SERVER_URL || 'http://o-mind-api:8000';
}

function getApiKey(ctx) {
  return ctx?.config?.apiKey || process.env.MEMORY_API_KEY || 'key-prod-1';
}

// 调用 O-Mind API
async function callOMind(path, method = 'GET', body = null, ctx) {
  const url = getMemoryUrl(ctx);
  const key = getApiKey(ctx);
  
  try {
    const res = await fetch(`${url}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-API-Key': key },
      body: body ? JSON.stringify(body) : undefined
    });
    return await res.json();
  } catch (e) {
    console.error('[O-Mind] API error:', e.message);
    return null;
  }
}

export default {
  id: PLUGIN_ID,
  name: 'O-Mind',
  description: '私有化部署的本地记忆服务',
  kind: 'memory',
  
  configSchema: {
    type: 'object',
    properties: {
      memoryServerUrl: { type: 'string', default: 'http://o-mind-api:8000' },
      apiKey: { type: 'string', default: 'key-prod-1' }
    }
  },
  
  register(api) {
    console.log('[O-Mind] Registering tools...');
    
    // save_memory tool
    api.registerTool(
      (ctx) => ({
        name: 'save_memory',
        description: '保存重要记忆到本地 O-Mind 服务器',
        inputSchema: {
          type: 'object',
          properties: {
            content: { type: 'string', description: '要保存的记忆内容' },
            tags: { type: 'array', items: { type: 'string' }, description: '标签' },
            agent_id: { type: 'string', description: 'Agent ID' }
          },
          required: ['content']
        },
        handler: async (args) => {
          const result = await callOMind('/api/memories', 'POST', {
            content: args.content,
            tags: args.tags || [],
            source: 'plugin',
            agent_id: args.agent_id || 'openclaw'
          }, ctx);
          return result ? { success: true, id: result.id, message: '记忆已保存' } : { success: false };
        }
      }),
      { names: ['save_memory'] }
    );
    
    // get_memories tool
    api.registerTool(
      (ctx) => ({
        name: 'get_memories',
        description: '获取所有记忆列表',
        inputSchema: {
          type: 'object',
          properties: {
            limit: { type: 'number', default: 50 },
            agent_id: { type: 'string' }
          }
        },
        handler: async (args) => {
          let path = `/api/memories?limit=${args.limit || 50}`;
          if (args.agent_id) path += `&agent_id=${args.agent_id}`;
          const results = await callOMind(path, 'GET', null, ctx);
          return { success: true, memories: results || [] };
        }
      }),
      { names: ['get_memories'] }
    );
    
    // search_memories tool
    api.registerTool(
      (ctx) => ({
        name: 'search_memories',
        description: '搜索相关记忆',
        inputSchema: {
          type: 'object',
          properties: {
            query: { type: 'string', description: '搜索关键词' },
            limit: { type: 'number', default: 10 }
          },
          required: ['query']
        },
        handler: async (args) => {
          const results = await callOMind(`/api/memories?q=${encodeURIComponent(args.query)}&limit=${args.limit || 10}`, 'GET', null, ctx);
          return { success: true, memories: results || [] };
        }
      }),
      { names: ['search_memories'] }
    );
    
    // get_stats tool
    api.registerTool(
      (ctx) => ({
        name: 'get_stats',
        description: '获取记忆统计信息',
        inputSchema: { type: 'object', properties: {} },
        handler: async () => {
          const stats = await callOMind('/api/stats', 'GET', null, ctx);
          return { success: true, stats };
        }
      }),
      { names: ['get_stats'] }
    );
    
    console.log('[O-Mind] Tools registered');
  }
};
