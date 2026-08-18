#!/usr/bin/env python3
"""
二次元趣闻采集管道 - 一键调度器
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
用法:
  python3 run_pipeline.py              # 完整管道（采集→富化→写入）
  python3 run_pipeline.py --scrape     # 仅采集
  python3 run_pipeline.py --enrich     # 仅富化（用今天的原始数据）
  python3 run_pipeline.py --send       # 仅写入 Notion（用今天的富化数据）
  python3 run_pipeline.py --dedup-only # 仅去重统计，不执行其他步骤
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / "output"
DEDUP_FILE = OUTPUT_DIR / "dedup_cache.json"


def load_dotenv():
    """加载 .env 文件"""
    env = {}
    p = PROJECT_DIR / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return {**os.environ, **env}


ENV = load_dotenv()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def run_script(script_name: str, extra_args: list = None) -> int:
    """运行项目内的 Python 脚本"""
    cmd = [sys.executable, str(PROJECT_DIR / script_name)]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*50}")
    print(f"🚀 执行: {' '.join(cmd)}")
    print(f"{'='*50}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


# ═══════════════════════════════════════════════
# 去重逻辑
# ═══════════════════════════════════════════════

def load_dedup_cache() -> set:
    """加载已采集的 BV 号集合"""
    if DEDUP_FILE.exists():
        try:
            data = json.loads(DEDUP_FILE.read_text())
            return set(data.get("bv_ids", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def save_dedup_cache(bv_ids: set, stats: dict):
    """保存去重缓存"""
    DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEDUP_FILE.write_text(json.dumps({
        "bv_ids": sorted(bv_ids),
        "stats": stats,
        "updated_at": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2))
    print(f"  💾 去重缓存已更新: {DEDUP_FILE}")


def filter_dedup(items: list) -> tuple:
    """
    过滤已有 BV 号，返回 (新条目, 去重统计)
    """
    cache = load_dedup_cache()
    new_items = []
    skipped = 0
    for item in items:
        bvid = item.get("bvid", "")
        if bvid and bvid in cache:
            skipped += 1
        else:
            if bvid:
                cache.add(bvid)
            new_items.append(item)

    stats = {
        "total_input": len(items),
        "new": len(new_items),
        "skipped_duplicate": skipped,
        "cache_size_before": len(cache) - len(new_items),
        "cache_size_after": len(cache),
    }
    return new_items, stats


def update_dedup_after_send(items: list):
    """
    写入 Notion 成功后，把成功写入的 BV 号加入去重缓存
    """
    cache = load_dedup_cache()
    new_bvs = [item.get("bvid", "") for item in items if item.get("bvid")]
    for bv in new_bvs:
        cache.add(bv)

    stats = {
        "total_in_cache": len(cache),
        "added_this_run": len(new_bvs),
    }
    save_dedup_cache(cache, stats)
    print(f"  ✅ 去重缓存: 已有 {len(cache)} 条, 本次新增 {len(new_bvs)} 条")


def dedup_report():
    """打印去重报告"""
    cache = load_dedup_cache()
    print(f"\n📊 去重报告:")
    print(f"   已缓存 BV 号: {len(cache)} 条")
    if cache:
        print(f"   缓存文件: {DEDUP_FILE}")
    else:
        print(f"   (首次运行，尚无缓存)")


# ═══════════════════════════════════════════════
# 主调度
# ═══════════════════════════════════════════════

def main():
    args = set(sys.argv[1:])

    # 仅去重报告
    if "--dedup-only" in args:
        dedup_report()
        return

    # 仅某个步骤
    if "--scrape" in args:
        rc = run_script("scrape.py")
        return

    if "--enrich" in args:
        today = today_str()
        raw_file = OUTPUT_DIR / f"{today}.json"
        if not raw_file.exists():
            print(f"❌ 找不到原始数据: {raw_file}")
            print(f"   先运行 python3 run_pipeline.py --scrape")
            return
        print(f"📂 使用原始数据: {raw_file}")
        rc = run_script("enrich.py", [str(raw_file)])
        return

    if "--send" in args:
        today = today_str()
        enriched_file = OUTPUT_DIR / f"{today}_enriched.json"
        if not enriched_file.exists():
            print(f"❌ 找不到富化数据: {enriched_file}")
            print(f"   先运行 python3 run_pipeline.py --enrich")
            return
        print(f"📂 使用富化数据: {enriched_file}")
        rc = run_script("send.py", [str(enriched_file)])
        return

    # ═══════════════════════════════════════════
    # 完整管道: scrape → enrich → dedup → send
    # ═══════════════════════════════════════════
    print(f"\n{'━'*50}")
    print(f"  🎬 二次元趣闻采集管道 - 完整运行")
    print(f"  📅 {today_str()}")
    print(f"{'━'*50}")

    # Step 1: 采集
    print(f"\n📡 [1/4] B站数据采集...")
    rc = run_script("scrape.py")
    if rc != 0:
        print(f"\n❌ 采集失败，退出码 {rc}")
        return

    today = today_str()
    raw_file = OUTPUT_DIR / f"{today}.json"
    enriched_file = OUTPUT_DIR / f"{today}_enriched.json"

    # Step 2: 富化
    print(f"\n🤖 [2/4] Gemini AI 富化评分...")
    rc = run_script("enrich.py", [str(raw_file)])
    if rc != 0:
        print(f"\n❌ 富化失败，退出码 {rc}")
        return

    # Step 3: 去重
    print(f"\n🔍 [3/4] 去重检查...")
    if not enriched_file.exists():
        print(f"❌ 富化文件不存在: {enriched_file}")
        return

    enriched_items = json.loads(enriched_file.read_text())
    print(f"   富化数据: {len(enriched_items)} 条")

    # 过滤 score >= 40 的条目
    qualified = [item for item in enriched_items if item.get("score", 0) >= 40]
    print(f"   评分≥40: {len(qualified)} 条")

    # 去重
    new_items, dedup_stats = filter_dedup(qualified)
    print(f"   去重前: {len(qualified)} 条")
    print(f"   去重后: {len(new_items)} 条 (跳过重复: {dedup_stats['skipped_duplicate']} 条)")

    if len(new_items) == 0:
        print(f"\n⚠️  没有新的未重复条目，跳过写入 Notion")
        dedup_report()
        save_dedup_cache(load_dedup_cache(), dedup_stats)
        return

    # 写回去重后的文件（供 send.py 使用）
    deduped_file = OUTPUT_DIR / f"{today}_deduped.json"
    deduped_file.write_text(json.dumps(new_items, ensure_ascii=False, indent=2))
    print(f"   💾 去重后数据: {deduped_file}")

    # Step 4: 写入 Notion
    print(f"\n📝 [4/4] 写入 Notion 数据库...")
    rc = run_script("send.py", [str(deduped_file)])
    if rc != 0:
        print(f"\n❌ 写入失败，退出码 {rc}")
        return

    # 更新去重缓存
    update_dedup_after_send(new_items)

    print(f"\n{'━'*50}")
    print(f"  ✅ 管道运行完成!")
    print(f"     采集 → 富化 → 去重 → Notion 写入")
    print(f"     本次新增: {len(new_items)} 条")
    print(f"{'━'*50}")


if __name__ == "__main__":
    main()