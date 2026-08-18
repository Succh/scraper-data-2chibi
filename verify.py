"""验证 Notion 内容字段是否已写入"""
import json, urllib.request, ssl
from pathlib import Path

env = {}
for line in Path('.env').read_text().splitlines():
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

TOKEN = env['NOTION_TOKEN']
DB_ID = '3c05a375-9092-8006-aad0-fd6a93507540'

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    f'https://api.notion.com/v1/databases/{DB_ID}/query',
    data=json.dumps({'page_size': 15}).encode(),
    headers={'Authorization': f'Bearer {TOKEN}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
data = json.loads(resp.read())

pages = data.get('results', [])
print(f'共 {len(pages)} 条记录\n')
print(f'{"#":>2} {"评分":>4} | 内容状态 | 内容预览')
print('-'*70)
empty_count = 0
for i, p in enumerate(pages[:15], 1):
    score = (p['properties'].get('评分', {}).get('number') or 0)
    content = ''
    rich = p['properties'].get('内容', {}).get('rich_text', [])
    if rich:
        content = rich[0].get('text', {}).get('content', '')
    if not content:
        empty_count += 1
    mark = '✅ 有内容' if content else '❌ 空'
    short = content[:35] + '...' if len(content) > 35 else content
    print(f'{i:>2} {score:>4} | {mark:<8} | {short}')
print(f'\n前15条中空内容数: {empty_count}')