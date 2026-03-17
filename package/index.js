/**
 * O-Mind Plugin - 完全对齐 mem9 格式
 */

const PLUGIN_ID = 'o-mind';

function getMemoryUrl() {
  return process.env.MEMORY_SERVER_URL || 'http://localhost:8000';
}

function getApiKey() {
  return process.env.MEMORY_API_KEY || 'key-prod-1';
}

async function callOMind(path, method = 'GET', body = null) {
  const url = getMemoryUrl();
  const key = getApiKey();
  
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
      memoryServerUrl: { type: 'string', default: 'http://localhost:8000' },
      apiKey: { type: 'string', default: 'key-prod-1' }
    }
  },
  
  register(api) {
    console.error('[O-Mind] Registering...');
    
    // ====== 工具注册 - 完全对齐 mem9 格式 ======
    const toolNames = ['save_memory', 'get_memories', 'search_memories', 'get_stats'];
    
    const tools = [
      {
        name: 'save_memory',
        label: 'Save Memory',
        description: '保存重要记忆到本地 O-Mind 服务器',
        parameters: {
          type: 'object',
          properties: {
            content: { type: 'string', description: '要保存的记忆内容' },
            tags: { type: 'array', items: { type: 'string' }, description: '标签' },
            source: { type: 'string', description: '来源' }
          },
          required: ['content']
        },
        execute: async (_id, params) => {
          const p = params || {};
          const result = await callOMind('/api/memories', 'POST', {
            content: p.content,
            tags: p.tags || [],
            source: p.source || 'plugin',
            agent_id: p.agent_id || 'openclaw'
          });
          return JSON.stringify({ ok: true, data: result });
        }
      },
      {
        name: 'get_memories',
        label: 'Get Memories',
        description: '获取所有记忆列表',
        parameters: {
          type: 'object',
          properties: {
            limit: { type: 'number', description: '返回数量' },
            agent_id: { type: 'string', description: 'Agent ID' }
          }
        },
        execute: async (_id, params) => {
          const p = params || {};
          let path = `/api/memories?limit=${p.limit || 50}`;
          if (p.agent_id) path += `&agent_id=${p.agent_id}`;
          const results = await callOMind(path);
          return JSON.stringify({ ok: true, data: results || [] });
        }
      },
      {
        name: 'search_memories',
        label: 'Search Memories',
        description: '搜索相关记忆',
        parameters: {
          type: 'object',
          properties: {
            q: { type: 'string', description: '搜索关键词' },
            limit: { type: 'number', description: '返回数量' }
          },
          required: ['q']
        },
        execute: async (_id, params) => {
          const p = params || {};
          const results = await callOMind(`/api/memories?q=${encodeURIComponent(p.q)}&limit=${p.limit || 10}`);
          return JSON.stringify({ ok: true, data: results || [] });
        }
      },
      {
        name: 'get_stats',
        label: 'Get Stats',
        description: '获取记忆统计信息',
        parameters: {
          type: 'object',
          properties: {}
        },
        execute: async (_id, params) => {
          const stats = await callOMind('/api/stats');
          return JSON.stringify({ ok: true, data: stats });
        }
      }
    ];
    
    // 注册所有工具
    api.registerTool(() => tools, { names: toolNames });
    
    // ====== Hook 注册 - 完全对齐 mem9 格式 ======
    
    // before_prompt_build - 注入记忆到上下文 (完全对齐 mem9)
    api.on('before_prompt_build', async (event) => {
      try {
        const evt = event || {};
        const prompt = evt?.prompt;
        if (!prompt || prompt.length < 5) return;
        
        const result = await callOMind(`/api/memories?q=${encodeURIComponent(prompt.slice(0, 100))}&limit=10`);
        const memories = result || [];
        
        if (memories.length === 0) return;
        
        console.error(`[O-Mind] ✅ 注入 ${memories.length} 条记忆到 LLM 上下文`);
        
        return {
          prependContext: memories.map(m => `- ${m.content}`).join('\n'),
        };
      } catch (err) {
        console.error(`[O-Mind] before_prompt_build failed: ${String(err)}`);
      }
    }, { priority: 50 });
    
    // agent_end - 保存对话
    api.on('agent_end', async (event, context) => {
      try {
        const evt = event || {};
        const ctx = context || {};
        if (!evt.messages || evt.messages.length === 0) return;
        
        for (const msg of evt.messages) {
          if (!msg || typeof msg !== 'object') continue;
          
          // 只处理用户消息
          if (msg.role !== 'user') continue;
          
          let content = '';
          if (typeof msg.content === 'string') {
            content = msg.content;
          } else if (Array.isArray(msg.content)) {
            for (const block of msg.content) {
              if (block?.type === 'text' && block?.text) {
                content += block.text;
              }
            }
          }
          
          // 严格过滤：只保存纯文本用户消息
          if (!content || content.length < 3 || content.length > 500) continue;
          if (content.startsWith('{') || content.startsWith('[') || content.startsWith('#')) continue;
          if (content.startsWith('用户说:') || content.startsWith('- ')) continue;
          if (content.includes('Conversation') || content.includes('System:') || content.includes('_meta')) continue;
          if (content.includes('message_id') || content.includes('sender')) continue;
          if (content.includes('Pre-compaction') || content.includes('memory flush')) continue;
          if (content.includes('HEARTBEAT') || content.includes('BOOTSTRAP')) continue;
          
          await callOMind('/api/memories', 'POST', {
            content: content.slice(0, 200),
            tags: ['user-message', 'hook'],
            source: 'o-mind-hook',
            agent_id: ctx.sessionKey || ctx.sessionId || 'unknown'
          });
          console.error('[O-Mind] User message saved:', content.slice(0, 30));
        }
      } catch (err) {
        console.error(`[O-Mind] agent_end failed: ${String(err)}`);
      }
    }, { priority: 50 });
    
    console.error('[O-Mind] Tools and hooks registered (mem9 style)');
  }
};
