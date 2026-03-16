/**
 * O-Mind Plugin
 * 私有化部署的本地记忆服务
 * 
 * 自动注入记忆到 prompt 上下文
 */

const PLUGIN_ID = 'o-mind';

// 获取配置
function getConfig() {
  const memoryServerUrl = process.env.MEMORY_SERVER_URL || 'http://localhost:8000';
  const apiKey = process.env.MEMORY_API_KEY || 'default';
  return { memoryServerUrl, apiKey };
}

// 调用 O-Mind API
async function callApi(path, method = 'GET', body = null) {
  const { memoryServerUrl, apiKey } = getConfig();
  const url = `${memoryServerUrl}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey
  };
  
  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);
  
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      console.error(`[O-Mind] API error: ${response.status}`);
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('[O-Mind] API call failed:', error.message);
    return null;
  }
}

// Plugin 入口
module.exports = {
  plugin: {
    id: PLUGIN_ID,
    name: 'O-Mind',
    version: '1.0.0',
    
    // 配置
    config: {
      memoryServerUrl: {
        type: 'string',
        default: 'http://localhost:8000',
        description: 'O-Mind API 服务器地址'
      },
      apiKey: {
        type: 'string',
        default: 'default',
        description: 'API Key'
      }
    },
    
    // 工具
    tools: {
      save_memory: {
        description: '保存重要记忆到本地 O-Mind 服务器',
        inputSchema: {
          type: 'object',
          properties: {
            content: {
              type: 'string',
              description: '要保存的记忆内容'
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: '标签'
            },
            agent_id: {
              type: 'string',
              description: 'Agent ID'
            }
          },
          required: ['content']
        },
        handler: async ({ content, tags = [], agent_id = 'openclaw' }) => {
          const result = await callApi('/api/memories', 'POST', {
            content,
            tags,
            source: 'plugin',
            agent_id
          });
          if (result) {
            return { success: true, id: result.id, message: '记忆已保存' };
          }
          return { success: false, error: '保存失败' };
        }
      },
      
      get_memories: {
        description: '获取所有记忆列表',
        inputSchema: {
          type: 'object',
          properties: {
            limit: { type: 'number', default: 50 },
            agent_id: { type: 'string' }
          }
        },
        handler: async ({ limit = 50, agent_id = '' }) => {
          let path = `/api/memories?limit=${limit}`;
          if (agent_id) path += `&agent_id=${agent_id}`;
          const results = await callApi(path);
          return { success: true, memories: results || [] };
        }
      },
      
      search_memories: {
        description: '搜索相关记忆',
        inputSchema: {
          type: 'object',
          properties: {
            query: { type: 'string', description: '搜索关键词' },
            limit: { type: 'number', default: 10 }
          },
          required: ['query']
        },
        handler: async ({ query, limit = 10 }) => {
          const results = await callApi(`/api/memories?q=${encodeURIComponent(query)}&limit=${limit}`);
          return { success: true, memories: results || [] };
        }
      },
      
      get_stats: {
        description: '获取记忆统计信息',
        inputSchema: { type: 'object', properties: {} },
        handler: async () => {
          const stats = await callApi('/api/stats');
          return { success: true, stats };
        }
      }
    },
    
    // 自动注入记忆到 prompt
    hooks: {
      before_prompt_build: async (context) => {
        const userMessage = context.userMessage || '';
        if (!userMessage) return { injectedContext: '' };
        
        // 提取关键词搜索
        const keywords = userMessage.slice(0, 100).replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ').trim();
        if (!keywords) return { injectedContext: '' };
        
        const memories = await callApi(`/api/memories?q=${encodeURIComponent(keywords)}&limit=5`);
        if (!memories || memories.length === 0) {
          return { injectedContext: '' };
        }
        
        const contextText = memories.map(m => `- ${m.content}`).join('\n');
        return { injectedContext: `## 相关记忆\n${contextText}` };
      },
      
      agent_end: async (context) => {
        const response = context.finalResponse || '';
        if (!response) return;
        
        // 保存对话摘要
        await callApi('/api/memories', 'POST', {
          content: response.slice(0, 1000),
          tags: ['agent-response', 'plugin'],
          source: 'o-mind-plugin'
        });
      }
    }
  }
};
