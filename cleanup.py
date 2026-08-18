"""删除 Notion 数据库中空内容的旧记录"""
import json, urllib.request, ssl, time
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

# 1. 查询所有记录
all_pages = []
next_cursor = None
while True:
    body = json.dumps({'page_size': 100}).encode()
    if next_cursor:
        body = json.dumps({'page_size': 100, 'start_cursor': next_cursor}).encode()
    req = urllib.request.Request(
        f'https://api.notion.com/v1/databases/{DB_ID}/query',
        data=body, headers=HEADERS, method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
    data = json.loads(resp.read())
    pages = data.get('results', [])
    all_pages.extend(pages)
    if data.get('has_more'):
        next_cursor = data['next_cursor']
    else:
        break

print(f'共查询到 {len(all_pages)} 条记录\n')

# 2. 找出内容为空的记录
empty_pages = []
for p in all_pages:
    content_rich = p['properties'].get('内容', {}).get('rich_text', [])
    if not content_rich or not content_rich[0].get('text', {}).get('content', '').strip():
        empty_pages.append(p)

print(f'内容为空的记录: {len(empty_pages)} 条')
if empty_pages:
    print('待删除列表:')
    for p in empty_pages:
        title = ''
        t = p['properties'].get('Name', {}).get('title', [])
        if t:
            title = t[0].get('text', {}).get('content', '')
        score = p['properties'].get('评分', {}).get('number', '?')
        print(f'  - score={score} | {title[:50]}...')

# 3. 逐条删除
if empty_pages:
    print(f'\n开始删除 {len(empty_pages)} 条...')
    deleted = 0
    for p in empty_pages:
        page_id = p['id']
        title = ''
        t = p['properties'].get('Name', {}).get('title', [])
        if t:
            title = t[0].get('text', {}).get('content', '')[:30]

        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    f'https://api.notion.com/v1/pages/{page_id}',
                    data=b'{}', headers=HEADERS, method='PATCH'
                )
                resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
                data = json.loads(resp.read())
                if data.get('archived') is True:
                    deleted += 1
                    print(f'  ✅ [{deleted}/{len(empty_pages)}] {title}...')
                    break
            except urllib.error.HTTPError as e:
                msg = json.loads(e.read().decode())
                print(f'  ❌ {title}... -> {msg.get("message", "")[:60]}')
                break
            except Exception:
                if attempt == 2:
                    print(f'  ❌ {title}... -> 超时')
                else:
                    time.sleep(2)

        time.sleep(0.3)
    print(f'\n🎉 删除完成！共删除 {deleted}/{len(empty_pages)} 条空内容记录')
else:
    print('没有空内容记录需要删除 ✅')