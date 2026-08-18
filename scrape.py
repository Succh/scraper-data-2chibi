#!/usr/bin/env python3
"""
二次元趣闻每日采集器 v3 - 生产级版
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
采集: B站搜索 API → 抓取二次元相关热门视频
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

# 二次元趣闻关键词（合法合规，仅限公开内容）
KEYWORDS = [
    "二次元 趣闻", "新番 推荐", "追番 日常",
    "cosplay 整活", "动漫 梗", "Vtuber 搞笑",
]

# 分类 → 关键词映射（用于根据反馈调整搜索策略）
CAT_KEYWORDS = {
    "日本文化": ["日本文化", "日系社会", "日本趣事"],
    "声优": ["声优", "配音演员", "声优趣事"],
    "游戏": ["原神", "明日方舟", "游戏梗", "游戏趣闻"],
    "动漫梗": ["动漫梗", "二次元梗", "名场面"],
    "新番": ["新番", "动画推荐", "追番"],
    "业界": ["动漫业界", "动画公司", "业界新闻"],
    "Cosplay": ["cosplay", "漫展", "二次元穿搭"],
    "Vtuber": ["Vtuber", "虚拟主播", "vtuber搞笑"],
    "综合": ["二次元", "动漫", "acg"],
}


def load_feedback_adjusted_keywords():
    """
    读取 feedback.json，根据用户偏好调整关键词权重。
    返回调整后的关键词列表（更多偏好的词，减少不喜欢的词）。
    """
    feedback_path = OUTPUT_DIR / "feedback.json"
    if not feedback_path.exists():
        return KEYWORDS
    
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            feedbacks = json.load(f)
    except (json.JSONDecodeError, IOError):
        return KEYWORDS
    
    if not feedbacks:
        return KEYWORDS
    
    # 读取已有富化数据建立 bvid -> category 映射
    from datetime import datetime as dt
    today = dt.now().strftime("%Y-%m-%d")
    enriched_path = OUTPUT_DIR / f"{today}_enriched.json"
    bvid_to_cat = {}
    if enriched_path.exists():
        try:
            with open(enriched_path, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
            for item in prev_data:
                bvid_to_cat[item.get("bvid", "")] = item.get("category", "其他")
        except (json.JSONDecodeError, IOError):
            pass
    
    # 按分类统计 like/dislike
    cat_stats = {}
    for fb in feedbacks:
        bvid = fb.get("bvid", "")
        action = fb.get("action", "")
        cat = bvid_to_cat.get(bvid, "其他")
        if cat not in cat_stats:
            cat_stats[cat] = {"like": 0, "dislike": 0}
        if action == "like":
            cat_stats[cat]["like"] += 1
        elif action == "dislike":
            cat_stats[cat]["dislike"] += 1
    
    # 调整关键词
    adjusted = list(KEYWORDS)  # 基础关键词始终保留
    boost_cats = []
    reduce_cats = []
    
    for cat, stats in cat_stats.items():
        total = stats["like"] + stats["dislike"]
        if total < 2:
            continue  # 样本太少，跳过
        like_ratio = stats["like"] / total
        if like_ratio >= 0.7:
            boost_cats.append(cat)
            # 添加该分类的额外关键词（最多3个）
            extra = CAT_KEYWORDS.get(cat, [])
            adjusted.extend(extra[:3])
        elif like_ratio <= 0.3:
            reduce_cats.append(cat)
            # 从列表中移除该分类的关键词
            cat_kws = CAT_KEYWORDS.get(cat, [])
            adjusted = [k for k in adjusted if k not in cat_kws]
    
    if boost_cats or reduce_cats:
        print(f"📊 搜索关键词根据反馈调整:")
        if boost_cats:
            print(f"   ⬆️ 增加: {', '.join(boost_cats)}")
        if reduce_cats:
            print(f"   ⬇️ 减少: {', '.join(reduce_cats)}")
        print(f"   🔍 关键词数: {len(KEYWORDS)} → {len(adjusted)}")
    
    return adjusted

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

# 从环境变量加载 B 站 Cookie（可选，用于反爬）
_BILI_COOKIE = _ENV.get("BILI_COOKIE", "")
if _BILI_COOKIE:
    HEADERS["Cookie"] = _BILI_COOKIE
    print("✅ 已加载 B 站 Cookie")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


# ═══════════════════════════════════════════════
# 第一层：采集
# ═══════════════════════════════════════════════
def scrape_bilibili(keyword: str, page: int = 1, pages: int = 2) -> list:
    """从 B 站搜索 API 抓取视频数据"""
    results = []
    for p in range(1, pages + 1):
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": p,
            "order": "click",  # 按热度排序
            "duration": "0",
        }
        url = f"https://api.bilibili.com/x/web-interface/search/type?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
                data = json.loads(resp.read())
            if data.get("code") != 0:
                print(f"  ⚠️  [{keyword}] 第{p}页 API 返回 code={data.get('code')}")
                break

            for item in data.get("data", {}).get("result", []):
                aid = item.get("aid")
                if not aid or aid in {r.get("aid") for r in results}:
                    continue
                results.append({
                    "aid": aid,
                    "title": item.get("title", "").strip(),
                    "desc": (item.get("desc") or "").strip(),
                    "author": item.get("author", ""),
                    "play": item.get("play", 0),
                    "danmaku": item.get("danmaku", 0),
                    "pub_time": datetime.fromtimestamp(
                        item.get("pubdate", 0)
                    ).strftime("%Y-%m-%d %H:%M") if item.get("pubdate") else "",
                    "url": f"https://www.bilibili.com/video/{'av' + str(aid)}",
                    "source": f"B站 · {keyword}",
                })
        except Exception as e:
            print(f"  ❌ [{keyword}] 第{p}页: {e}")

        time.sleep(1.5)  # 反爬：错峰
    return results


def scrape_all() -> list:
    """遍历所有关键词（根据反馈调整后），去重后返回"""
    # 根据用户反馈调整关键词
    keywords = load_feedback_adjusted_keywords()
    all_items = []
    seen_aid = set()
    for kw in keywords:
        print(f"🔍 抓取: {kw}")
        items = scrape_bilibili(kw)
        for item in items:
            if item["aid"] not in seen_aid:
                seen_aid.add(item["aid"])
                all_items.append(item)
        print(f"  → 新增 {len(items)} 条")
        time.sleep(1)
    return all_items


# ═══════════════════════════════════════════════
# 第二层：Gemini AI 富化
# ═══════════════════════════════════════════════
def enrich_with_gemini(items: list, batch_size: int = 5) -> list:
    """用 Gemini 对内容做分类、评分、摘要"""
    if not GEMINI_KEY:
        print("⚠️  未配置 GEMINI_API_KEY，跳过 AI 富化")
        for item in items:
            item["category"] = "未分类"
            item["score"] = 0
            item["summary"] = item.get("title", "")[:50]
        return items

    enriched = []
    # 每批处理 batch_size 条
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        print(f"  🧠 AI 富化 第 {i//batch_size + 1} 批 ({len(batch)} 条)")

        # 构建 prompt
        examples = []
        for j, item in enumerate(batch, 1):
            examples.append(
                f'{j}. 【{item["title"]}】'
                f'来源:{item["source"]} 作者:{item["author"]}'
                f'播放:{item["play"]} 弹幕:{item["danmaku"]}'
                f'简介:{(item["desc"] or "")[:80]}'
            )

        prompt = f"""你是二次元趣闻内容专家。请对以下 {len(batch)} 条内容逐条分析，
返回严格 JSON 数组（不要有其他文字），格式：
[{
  "category": "分类标签（新番/动漫梗/Cosplay/Vtuber/游戏/声优/漫展/业界/其他）",
  "score": 0-100的有趣程度评分,
  "summary": "一句话趣闻摘要，口语化，带emoji"
}]

请判断内容是否适合"二次元趣闻日报"（剔除纯教程、广告、低质内容），不适合的 score 设为 0。

内容列表：
{chr(10).join(examples)}"""

        # 调用 Gemini
        result = call_gemini(prompt)
        if result:
            try:
                data = json.loads(result)
                for item, score_data in zip(batch, data):
                    item["category"] = score_data.get("category", "未分类")
                    item["score"] = score_data.get("score", 0)
                    item["summary"] = score_data.get("summary", item.get("title", "")[:50])
            except json.JSONDecodeError:
                print(f"  ⚠️  Gemini 返回非 JSON，降级处理")
                for item in batch:
                    item["category"] = "未分类"
                    item["score"] = 0
                    item["summary"] = item.get("title", "")[:50]
        else:
            print(f"  ⚠️  Gemini 调用失败，降级处理")
            for item in batch:
                item["category"] = "未分类"
                item["score"] = 0
                item["summary"] = item.get("title", "")[:50]

        enriched.extend(batch)
        time.sleep(2)  # 免费 API 限流

    return enriched


def call_gemini(prompt: str) -> str | None:
    """调用 Gemini 3 Flash Preview API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_KEY}"
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  ❌ Gemini 错误: {str(e)[:200]}")
        return None


# ═══════════════════════════════════════════════
# 第三层：写入 Notion
# ═══════════════════════════════════════════════
def write_to_notion(items: list):
    """写入 Notion 数据库（自动创建页面）"""
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("⚠️  未配置 Notion，跳过写入")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    count = 0

    for item in items:
        if item.get("score", 0) == 0:
            continue  # 跳过评分为 0 的

        payload = json.dumps({
            "parent": {"database_id": NOTION_DB_ID},
            "properties": {
                "标题": {"title": [{"text": {"content": item["summary"]}}]},
                "原文": {"rich_text": [{"text": {"content": item["title"]}}]},
                "分类": {"select": {"name": item.get("category", "其他")}},
                "评分": {"number": item.get("score", 0)},
                "来源": {"rich_text": [{"text": {"content": item.get("source", "")}}]},
                "链接": {"url": item.get("url", "")},
                "作者": {"rich_text": [{"text": {"content": item.get("author", "")}}]},
                "采集日期": {"date": {"start": today}},
            }
        }).encode()

        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=payload,
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                print(f"  ✅ Notion: {item['summary'][:30]}... (id={result['id'][:8]}...)")
                count += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print(f"  ❌ Notion {item['summary'][:20]}...: {body}")
        except Exception as e:
            print(f"  ❌ Notion 错误: {e}")

        time.sleep(0.5)

    print(f"\n📊 写入 Notion 完成: {count} 条")


# ═══════════════════════════════════════════════
# 输出本地文件
# ═══════════════════════════════════════════════
def save_local(items: list):
    today = datetime.now().strftime("%Y-%m-%d")

    # JSON
    json_path = OUTPUT_DIR / f"{today}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON: {json_path}")

    # Markdown
    md_lines = [f"# 🎌 二次元趣闻日报 · {today}\n",
                f"> 共采集 {len([i for i in items if i.get('score', 0) > 0])} 条 | "
                f"AI 评分过滤 | 数据来源: B站\n"]

    # 按分类分组
    categories = {}
    for item in items:
        if item.get("score", 0) == 0:
            continue
        cat = item.get("category", "其他")
        categories.setdefault(cat, []).append(item)

    for cat, cat_items in sorted(categories.items(), key=lambda x: -sum(i["score"] for i in x[1])):
        md_lines.append(f"\n## 🏷️ {cat} ({len(cat_items)}条)\n")
        for item in sorted(cat_items, key=lambda x: -x["score"]):
            emoji_map = {"新番": "📺", "动漫梗": "😂", "Cosplay": "📸",
                         "Vtuber": "🎤", "游戏": "🎮", "声优": "🎙️",
                         "漫展": "🎪", "业界": "📰"}
            emoji = emoji_map.get(cat, "✨")
            md_lines.append(
                f"{emoji} **{item['summary']}**  "
                f"(评分:{item['score']} | [{item.get('author','')}]"
                f"({item.get('url','')}) | 播放:{item.get('play','')})\n"
            )

    md_path = OUTPUT_DIR / f"{today}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"💾 Markdown: {md_path}")

    return json_path, md_path


# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════
def main():
    print("=" * 50)
    print("🎌 二次元趣闻采集器 v3")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # 1. 采集
    print("\n📡 阶段一：采集")
    items = scrape_all()
    print(f"\n✅ 共采集 {len(items)} 条")

    if not items:
        print("❌ 无数据，退出")
        return

    # 2. AI 富化
    print("\n🧠 阶段二：AI 富化")
    items = enrich_with_gemini(items)
    scored = [i for i in items if i.get("score", 0) > 0]
    print(f"✅ 富化完成: {len(scored)}/{len(items)} 条有效")

    # 3. 写入 Notion
    print("\n📋 阶段三：写入 Notion")
    write_to_notion(items)

    # 4. 本地存储
    print("\n💾 阶段四：本地存储")
    save_local(items)

    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()
