#!/usr/bin/env python3
"""
二次元趣闻每日采集器 v4 - 使用 B 站公开 API（无需登录）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
采集: B 站动画分区新番 + 热门视频 → 过滤二次元相关内容
AI富化: Gemini 3 Flash 评分 + 分类 + 摘要
存储: 自动写入 Notion 数据库 + 本地 JSON/Markdown
定时: 可部署到 GitHub Actions 每日执行
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from pathlib import Path

# ── 配置 ──────────────────────────────────────
def _load_dotenv():
    _env = {}
    p = Path(__file__).parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                _env[k.strip()] = v.strip()
    return _env

_ENV = {**os.environ, **_load_dotenv()}
GEMINI_KEY = _ENV.get("GEMINI_API_KEY", "")
NOTION_TOKEN = _ENV.get("NOTION_TOKEN", "")
NOTION_DB_ID = _ENV.get("NOTION_DATABASE_ID", "")

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# B 站动画分区 rid
# rid=1: 动画, rid=13: 番剧, rid=167: 国创, rid=3: 音乐, rid=129: 舞蹈
# rid=4: 游戏, rid=36: 知识, rid=188: 科技, rid=234: 运动
ANIME_RIDS = [1, 13, 167]  # 动画 + 番剧 + 国创

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def fetch_url(url: str) -> dict | None:
    """通用 GET JSON 请求"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            data = json.loads(resp.read())
        return data
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:100]}")
        return None


def scrape_anime_newlist(rid: int = 1, pages: int = 2) -> list:
    """从 B 站分区最新视频 API 抓取动画相关视频"""
    results = []
    for p in range(1, pages + 1):
        url = f"https://api.bilibili.com/x/web-interface/newlist?rid={rid}&type=0&pn={p}&ps=20"
        data = fetch_url(url)
        if not data or data.get("code") != 0:
            break
        archives = data.get("data", {}).get("archives", [])
        for item in archives:
            results.append({
                "bvid": item.get("bvid", ""),
                "aid": item.get("aid"),
                "title": item.get("title", ""),
                "desc": item.get("desc", ""),
                "pic": item.get("pic", ""),
                "duration": item.get("duration", 0),
                "pubdate": item.get("pubdate", 0),
                "tname": item.get("tname", ""),
                "up_name": item.get("owner", {}).get("name", ""),
                "up_mid": item.get("owner", {}).get("mid", 0),
                "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                "source": f"B站-{item.get('tname', '动画')}",
                "play": item.get("stat", {}).get("view", 0),
                "danmaku": item.get("stat", {}).get("danmaku", 0),
                "like": item.get("stat", {}).get("like", 0),
                "coin": item.get("stat", {}).get("coin", 0),
            })
    return results


def scrape_popular(page: int = 1) -> list:
    """从 B 站热门视频 API 抓取（按播放量排序）"""
    url = f"https://api.bilibili.com/x/web-interface/popular?ps=20&pn={page}"
    data = fetch_url(url)
    if not data or data.get("code") != 0:
        return []
    results = []
    for item in data.get("data", {}).get("list", []):
        results.append({
            "bvid": item.get("bvid", ""),
            "aid": item.get("aid"),
            "title": item.get("title", ""),
            "desc": item.get("desc", ""),
            "pic": item.get("pic", ""),
            "duration": item.get("duration", 0),
            "pubdate": item.get("pubdate", 0),
            "tname": item.get("tname", ""),
            "up_name": item.get("owner", {}).get("name", ""),
            "up_mid": item.get("owner", {}).get("mid", 0),
            "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
            "source": "B站-热门",
            "play": item.get("stat", {}).get("view", 0),
            "danmaku": item.get("stat", {}).get("danmaku", 0),
            "like": item.get("stat", {}).get("like", 0),
            "coin": item.get("stat", {}).get("coin", 0),
        })
    return results


def dedup(items: list) -> list:
    """按 bvid 去重"""
    seen = set()
    result = []
    for item in items:
        bvid = item.get("bvid", "")
        if bvid and bvid not in seen:
            seen.add(bvid)
            result.append(item)
    return result


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🎌 二次元趣闻采集器 v4 - {today}")
    print("=" * 50)

    all_items = []

    # 1. 采集动画分区新番
    print("\n📺 [1/2] 采集动画分区新番...")
    for rid in ANIME_RIDS:
        items = scrape_anime_newlist(rid, pages=1)
        print(f"  ✅ rid={rid}: {len(items)} 条")
        all_items.extend(items)
        time.sleep(0.5)

    # 2. 采集热门视频
    print("\n🔥 [2/2] 采集热门视频...")
    popular = scrape_popular(page=1)
    print(f"  ✅ 热门: {len(popular)} 条")
    all_items.extend(popular)

    # 去重
    all_items = dedup(all_items)
    print(f"\n✅ 共采集 {len(all_items)} 条（去重后）")

    if not all_items:
        print("❌ 无数据，退出")
        return

    # 保存
    output_file = OUTPUT_DIR / f"{today}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"💾 原始数据: {output_file}")

    # 打印预览
    print("\n" + "=" * 50)
    print("📋 预览（前10条）：")
    print("=" * 50)
    for item in all_items[:10]:
        print(f"  [{item.get('source', '?')}] {item['title'][:50]}")


if __name__ == "__main__":
    main()
