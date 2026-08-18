"""
send.py - 将富化后的二次元趣闻数据写入 Notion 数据库
字段映射：summary→内容, title→Name, bvid→链接, source→来源, score→评分, category→分类
"""
import json, urllib.request, ssl, time, sys
from pathlib import Path
from datetime import datetime

env = {}
for line in Path('.env').read_text().splitlines():
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

TOKEN = env.get('NOTION_TOKEN', '')
DB_ID = '3c05a375-9092-8006-aad0-fd6a93507540'

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

def truncate_text(text, max_len=500):
    return text[:max_len] if len(text) > max_len else text

def build_link(bvid):
    """从 BV号生成 B站链接"""
    if bvid and bvid.startswith('BV'):
        return f'https://www.bilibili.com/video/{bvid}'
    return ''

def write_to_notion(items, date_str='2026-08-18'):
    if not items:
        print('⚠️ 无数据可写入')
        return 0

    success = 0
    for i, item in enumerate(items):
        title = str(item.get('title', '无标题'))[:100]
        summary = str(item.get('summary', ''))  # ← 关键修复：用 summary 不是 content
        source = str(item.get('source', ''))
        bvid = str(item.get('bvid', ''))
        score = item.get('score', 0)
        category = str(item.get('category', '其他'))
        link = build_link(bvid)

        props = {
            'Name': {'title': [{'text': {'content': title}}]},
            '内容': {'rich_text': [{'text': {'content': truncate_text(summary)}}]},
            '来源': {'rich_text': [{'text': {'content': truncate_text(source)}}]},
            '评分': {'number': score},
            '日期': {'date': {'start': date_str}},
            '分类': {'select': {'name': category}},
        }
        if link:
            props['链接'] = {'url': link}

        payload = json.dumps({
            'parent': {'database_id': DB_ID},
            'properties': props,
            'cover': {'type': 'external', 'external': {'url': item.get('pic', '')}} if item.get('pic') else None,
        }).encode()

        req = urllib.request.Request('https://api.notion.com/v1/pages', data=payload, headers=HEADERS)

        for attempt in range(3):  # 最多重试 3 次
            try:
                with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
                    data = json.loads(resp.read())
                    success += 1
                    print(f'  ✅ [{success}/{len(items)}] score={score:2d} | {title[:40]}...')
                    break
            except urllib.error.HTTPError as e:
                msg = json.loads(e.read().decode())
                print(f'  ❌ [{i+1}/{len(items)}] {title[:30]}... -> {msg.get("message", "")[:80]}')
                return success  # API错误不重试
            except Exception as ex:
                if attempt == 2:
                    print(f'  ❌ [{i+1}/{len(items)}] {title[:30]}... -> 网络超时(重试3次)')
                else:
                    time.sleep(3)

        time.sleep(0.3)
    return success

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else str(Path('output') / f"{datetime.now().strftime('%Y-%m-%d')}_enriched.json")
    date_str = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime('%Y-%m-%d')
    json_path = Path(input_file)
    if not json_path.exists():
        print(f'❌ 找不到数据文件: {json_path}')
        return

    with open(json_path) as f:
        items = json.load(f)

    print(f'📊 写入 {len(items)} 条数据到 Notion（日期: {date_str}）\n')
    success = write_to_notion(items, date_str=date_str)
    print(f'\n🎉 完成！成功 {success}/{len(items)} 条')

if __name__ == '__main__':
    main()