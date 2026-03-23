import re

with open('/app/api/topic_service.py', 'r') as f:
    content = f.read()

# 找到并替换问题代码
old = 'response = httpx.post(\n            f"{MINIMAX_BASE_URL}/text/chatcompletion_v2",'
new = '''api_url = f"{MINIMAX_BASE_URL}/text/chatcompletion_v2"
    
    try:
        response = httpx.post(
            api_url,'''

content = content.replace(old, new)

with open('/app/api/topic_service.py', 'w') as f:
    f.write(content)

print('Fixed')
