#!/usr/bin/env python3
"""
补充 B站视频详情数据（封面图、播放量、UP主等）
"""
import json
import time
import urllib.request
import ssl
from pathlib import Path

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
}
BASE = Path(__file__).parent

def fetch_video_info(bvid: str) -> dict:
    url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            data = json.loads(resp.read())
        d = data.get('data', {})
        if not d:
            return {}
        stat = d.get('stat', {})
        owner = d.get('owner', {})
        return {
            'pic': d.get('pic', ''),
            'author': owner.get('name', ''),
            'mid': owner.get('mid', 0),
            'play': stat.get('view', 0),
            'like': stat.get('like', 0),
            'danmaku': stat.get('danmaku', 0),
            'comment': stat.get('reply', 0),
            'coin': stat.get('coin', 0),
            'share': stat.get('share', 0),
            'favorite': stat.get('favorite', 0),
            'pubdate': d.get('pubdate', 0),
            'duration': d.get('duration', 0),
            'desc': d.get('desc', ''),
        }
    except Exception as e:
        print(f'  ⚠️  {bvid}: {type(e).__name__}')
        return {}

def format_play(n: int) -> str:
    if n >= 10000:
        return f'{n/10000:.1f}万'
    return str(n)

def main():
    enriched_path = BASE / 'output' / '2026-08-18_enriched.json'
    items = json.loads(enriched_path.read_text())
    print(f'共 {len(items)} 条，开始补充详情...')

    for i, item in enumerate(items):
        bvid = item.get('bvid', '')
        if not bvid:
            continue
        print(f'  [{i+1}/{len(items)}] {bvid}...', end=' ')
        info = fetch_video_info(bvid)
        item.update(info)
        item['play_display'] = format_play(info.get('play', 0))
        print('✓' if info else '✗')
        time.sleep(0.3)

    enriched_path.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    print(f'✓ 已保存到 {enriched_path.name}')

if __name__ == '__main__':
    main()
