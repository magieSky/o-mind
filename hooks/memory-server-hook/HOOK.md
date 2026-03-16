# memory-server-hook

在每次对话前自动检索记忆，对话后自动保存。

## Events

- prompt:build (before_prompt_build)
- command:reset (before_reset)
- agent:end (agent_end)

## Config

```json
{
  "memoryServerUrl": "http://memory-server:8000"
}
```

## 实现

这个 hook 会在以下时机调用 memory-server API:
1. before_prompt_build - 检索相关记忆注入上下文
2. before_reset - 保存会话摘要
3. agent_end - 保存对话内容
