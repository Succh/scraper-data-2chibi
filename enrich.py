#!/usr/bin/env python3
"""
AI 富化脚本：读取本地采集数据，用 Gemini 做分类/评分/摘要
用法: python3 enrich.py [输入文件路径]  （默认 output/今天的日期.json）
"""
import os, sys, json, time, urllib.request, ssl
from pathlib import Path
from datetime import datetime

# 安全读取 .env
def load_dotenv():
    env = {}
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

_env = {**os.environ, **load_dotenv()}
GEMINI_KEY = _env.get("GEMINI_API_KEY", "")
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

OUTPUT_DIR = Path(__file__).parent / "output"


def call_gemini(prompt: str) -> str | None:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-3-flash-preview:generateContent?key={GEMINI_KEY}")
    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"  ❌ Gemini 错误: {str(e)[:200]}")
        return None


def load_feedback_weights():
    """读取 feedback.json，计算每个分类的喜欢/不喜欢比率，返回权重提示"""
    feedback_path = OUTPUT_DIR / "feedback.json"
    if not feedback_path.exists():
        return {}
    
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            feedbacks = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    
    if not feedbacks:
        return {}
    
    # 读取已有的富化数据，建立 bvid -> category 映射
    today = datetime.now().strftime("%Y-%m-%d")
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
    
    # 计算权重：like 多的分类加权，dislike 多的分类降权
    weights = {}
    for cat, stats in cat_stats.items():
        total = stats["like"] + stats["dislike"]
        if total == 0:
            continue
        like_ratio = stats["like"] / total
        # like_ratio > 0.7: 加权；< 0.3: 降权
        if like_ratio >= 0.7 and stats["like"] >= 2:
            weights[cat] = "high"  # 用户喜欢这类，多推荐
        elif like_ratio <= 0.3 and stats["dislike"] >= 2:
            weights[cat] = "low"   # 用户不喜欢，少推荐
        else:
            weights[cat] = "normal"
    
    return weights


def build_feedback_hint(weights):
    """根据权重字典生成 prompt 提示"""
    if not weights:
        return ""
    
    high_cats = [cat for cat, w in weights.items() if w == "high"]
    low_cats = [cat for cat, w in weights.items() if w == "low"]
    
    hints = []
    if high_cats:
        hints.append(f"用户反馈显示喜欢【{'、'.join(high_cats)}】类内容，可适当放宽评分标准。")
    if low_cats:
        hints.append(f"用户反馈显示不喜欢【{'、'.join(low_cats)}】类内容，请严格评分，避免推荐。")
    
    return "\n".join(hints)

    # 读取反馈权重
    weights = load_feedback_weights()
    feedback_hint = build_feedback_hint(weights)
    if feedback_hint:
        print(f"📊 反馈权重: {weights}")

    # 挑前 20 条做富化（避免太多 token）
    batch = items[:20]
    print(f"🧠 对前 {len(batch)} 条做 AI 富化...")

    examples = []
    for i, item in enumerate(batch, 1):
        examples.append(
            f'{i}. 【{item["title"]}】'
            f'来源:{item.get("source","")} BV:{item.get("bvid","")}'
        )

    prompt = (
        "你是二次元趣闻内容专家。请对以下内容逐条分析，\n"
        "返回严格 JSON 数组（不要有其他文字），格式：\n"
        "[\n"
        '  {"category":"分类","score":0-100,"summary":"一句话趣闻摘要，口语化带emoji"}\n'
        "]\n\n"
        "分类标签范围：新番/动漫梗/Cosplay/Vtuber/游戏/声优/漫展/业界/日本文化/其他\n"
        "评分标准：0=不适合趣闻日报，100=超有趣必看\n"
        + (f"\n用户反馈偏好：\n{feedback_hint}\n" if feedback_hint else "")
        + "\n" + "\n".join(examples)
    )

    result = call_gemini(prompt)
    if not result:
        print("❌ Gemini 调用失败")
        return

    # 提取 JSON
    # 有时 Gemini 会在 JSON 前后加 ```json ... ```
    text = result.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        scores = json.loads(text)
    except json.JSONDecodeError:
        # 尝试找第一个 [ 到最后一个 ]
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            scores = json.loads(text[start:end + 1])
        else:
            print("❌ 无法解析 JSON")
            print(text[:500])
            return

    print(f"✅ AI 富化完成: {len(scores)} 条")

    # 合并结果
    enriched = []
    for item, score in zip(batch, scores):
        item["category"] = score.get("category", "其他")
        item["score"] = score.get("score", 0)
        item["summary"] = score.get("summary", item["title"][:50])
        enriched.append(item)

    # 输出 Markdown 日报
    today = "2026-08-18"
    lines = [f"# 🎌 二次元趣闻日报 · {today}\n",
             f"> AI 评分 + 分类 · Gemini 富化版\n"]

    scored = [i for i in enriched if i.get("score", 0) > 0]
    lines.append(f"\n共 {len(scored)} 条精选 · {len(enriched)} 条总计\n")

    categories = {}
    for item in scored:
        cat = item.get("category", "其他")
        categories.setdefault(cat, []).append(item)

    emoji_map = {"新番": "📺", "动漫梗": "😂", "Cosplay": "📸",
                 "Vtuber": "🎤", "游戏": "🎮", "声优": "🎙️",
                 "漫展": "🎪", "业界": "📰", "日本文化": "🇯🇵"}

    for cat, cat_items in sorted(categories.items(),
                                  key=lambda x: -sum(i["score"] for i in x[1])):
        emoji = emoji_map.get(cat, "✨")
        lines.append(f"\n## {emoji} {cat} ({len(cat_items)}条)\n")
        for item in sorted(cat_items, key=lambda x: -x["score"]):
            lines.append(f"- **{item['summary']}**  (评分:{item['score']})\n")

    md_path = OUTPUT_DIR / f"{today}_enriched.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"💾 富化日报: {md_path}")

    # 保存 JSON
    json_path = OUTPUT_DIR / f"{today}_enriched.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"💾 富化数据: {json_path}")

    # 打印预览
    print("\n" + "=" * 50)
    print("📋 预览（前10条精选）：")
    print("=" * 50)
    for item in sorted(scored, key=lambda x: -x["score"])[:10]:
        print(f"  [{item['score']}] {item['summary']}")


if __name__ == "__main__":
    main()
