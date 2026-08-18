#!/usr/bin/env python3
"""
二次元趣闻日报 HTML 生成器
从 enriched.json 生成一个好看的静态 HTML 浏览页面
"""

import json
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent / "output"

# 分类 emoji 映射
CATEGORY_EMOJI = {
    "新番动画": "🎬",
    "声优艺能": "🎙️",
    "漫画连载": "📖",
    "游戏梗": "🎮",
    "手办模型": "🎎",
    "cosplay": "👘",
    "Vtuber": "🤖",
    "同人创作": "🎨",
    "趣闻轶事": "🔥",
    "综合": "✨",
}

# 分类配色
CATEGORY_COLOR = {
    "新番动画": "#FF6B6B",
    "声优艺能": "#4ECDC4",
    "漫画连载": "#45B7D1",
    "游戏梗": "#96CEB4",
    "手办模型": "#FFEAA7",
    "cosplay": "#DDA0DD",
    "Vtuber": "#98D8C8",
    "同人创作": "#F7DC6F",
    "趣闻轶事": "#E17055",
    "综合": "#74B9FF",
}


def generate_html(data: list, date_str: str) -> str:
    # 按分数排序
    data.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 按分类分组
    categories = {}
    for item in data:
        cat = item.get("category", "综合")
        categories.setdefault(cat, []).append(item)

    # 生成卡片 HTML
    cards_html = []
    for cat, items in categories.items():
        emoji = CATEGORY_EMOJI.get(cat, "✨")
        color = CATEGORY_COLOR.get(cat, "#74B9FF")
        for item in items:
            score = item.get("score", 0)
            score_color = "#00b894" if score >= 70 else "#fdcb6e" if score >= 50 else "#b2bec3"
            bvid = item.get("bvid", "")
            pic = item.get("pic", "")
            title = item.get("title", "").replace('"', '&quot;')
            summary = item.get("summary", "").replace('"', '&quot;')
            author = item.get("author", "未知")
            play = item.get("play_display", item.get("play", 0))
            danmaku = item.get("danmaku", 0)

            cards_html.append(f'''
            <div class="card" data-cat="{cat}" data-score="{score}">
                <div class="card-img" style="background-image:url({pic})">
                    <span class="score-badge" style="background:{score_color}">{score}</span>
                    <span class="cat-badge" style="background:{color}">{emoji} {cat}</span>
                </div>
                <div class="card-body">
                    <h3 class="card-title">
                        <a href="https://www.bilibili.com/video/{bvid}" target="_blank">{title}</a>
                    </h3>
                    <p class="card-summary">{summary}</p>
                    <div class="card-meta">
                        <span>👤 {author}</span>
                        <span>▶️ {play}</span>
                        <span>💬 {danmaku}</span>
                    </div>
                </div>
            </div>
            ''')

    # 分类过滤器按钮
    cat_buttons = ['<button class="filter-btn active" data-cat="all">全部 ({})</button>'.format(len(data))]
    for cat, items in categories.items():
        emoji = CATEGORY_EMOJI.get(cat, "✨")
        cat_buttons.append(f'<button class="filter-btn" data-cat="{cat}">{emoji} {cat} ({len(items)})</button>')

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>二次元趣闻日报 - {date_str}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}
.header {{
    text-align: center;
    padding: 30px 20px;
    color: white;
}}
.header h1 {{ font-size: 2.2em; margin-bottom: 8px; text-shadow: 0 2px 4px rgba(0,0,0,.3); }}
.header p {{ opacity: .9; font-size: 1em; }}
.filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin: 20px 0;
}}
.filter-btn {{
    padding: 8px 16px;
    border: none;
    border-radius: 20px;
    background: rgba(255,255,255,.2);
    color: white;
    cursor: pointer;
    font-size: .9em;
    transition: all .2s;
}}
.filter-btn:hover, .filter-btn.active {{
    background: white;
    color: #764ba2;
    transform: scale(1.05);
}}
.stats {{
    text-align: center;
    color: rgba(255,255,255,.8);
    margin: 10px 0 20px;
    font-size: .9em;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}}
.card {{
    background: white;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,.1);
    transition: transform .2s, box-shadow .2s;
}}
.card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 8px 30px rgba(0,0,0,.15);
}}
.card.hidden {{ display: none; }}
.card-img {{
    width: 100%;
    height: 180px;
    background-size: cover;
    background-position: center;
    background-color: #f0f0f0;
    position: relative;
}}
.score-badge {{
    position: absolute;
    top: 8px;
    right: 8px;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: .85em;
    box-shadow: 0 2px 8px rgba(0,0,0,.3);
}}
.cat-badge {{
    position: absolute;
    bottom: 8px;
    left: 8px;
    padding: 4px 10px;
    border-radius: 12px;
    color: white;
    font-size: .75em;
    font-weight: 500;
}}
.card-body {{ padding: 14px; }}
.card-title {{ font-size: 1em; line-height: 1.4; margin-bottom: 6px; }}
.card-title a {{ color: #2d3436; text-decoration: none; }}
.card-title a:hover {{ color: #764ba2; }}
.card-summary {{
    font-size: .85em;
    color: #636e72;
    line-height: 1.5;
    margin-bottom: 10px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.card-meta {{
    display: flex;
    gap: 12px;
    font-size: .75em;
    color: #b2bec3;
}}
.footer {{
    text-align: center;
    padding: 30px;
    color: rgba(255,255,255,.6);
    font-size: .85em;
}}
@media (max-width: 640px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .header h1 {{ font-size: 1.6em; }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🎌 二次元趣闻日报</h1>
        <p>{date_str} · 共 {len(data)} 条精选</p>
    </div>
    <div class="filters">
        {" ".join(cat_buttons)}
    </div>
    <div class="stats">
        点击分类筛选 · 按评分排序 · 数据每日自动更新
    </div>
    <div class="grid">
        {"".join(cards_html)}
    </div>
    <div class="footer">
        Powered by 阿堰 · 数据来源 B站 · AI 富化 Gemini
    </div>
</div>
<script>
document.querySelectorAll(".filter-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const cat = btn.dataset.cat;
        document.querySelectorAll(".card").forEach(card => {{
            card.classList.toggle("hidden", cat !== "all" && card.dataset.cat !== cat);
        }});
    }});
}});
</script>
</body>
</html>
'''


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    input_file = OUTPUT_DIR / f"{today}_enriched.json"
    if not input_file.exists():
        print(f"❌ 文件不存在: {input_file}")
        return
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    html = generate_html(data, today)
    output_file = OUTPUT_DIR / f"{today}_report.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 日报页面: {output_file}")


if __name__ == "__main__":
    main()
