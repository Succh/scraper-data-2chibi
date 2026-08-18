"""快速删除空内容记录 - 激进版"""
import json, urllib.request, ssl, sys, time
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

HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}

# 读已保存的空记录ID列表
empty = json.load(open('/tmp/empty_pages.json'))
total = len(empty)
print(f'待删除: {total} 条', flush=True)

deleted = 0
failed = 0
for i, item in enumerate(empty):
    pid = item['id']
    title = item['title'][:30]
    try:
        req = urllib.request.Request(
            f'https://api.notion.com/v1/pages/{pid}',
            data=b'{"archived": true}', headers=HEADERS, method='PATCH'
        )
        resp = urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        data = json.loads(resp.read())
        if data.get('archived') is True:
            deleted += 1
        print(f'  [{deleted}/{total}] ✅ {title}', flush=True)
    except Exception as ex:
        failed += 1
        print(f'  [{i+1}/{total}] ❌ {title} -> {str(ex)[:50]}', flush=True)

    time.sleep(0.1)

print(f'\n🎉 完成！删除 {deleted} 条，失败 {failed} 条', flush=True)