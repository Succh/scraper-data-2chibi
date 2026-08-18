#!/usr/bin/env python3
"""
Supabase 存储后端 - 将富化数据写入 Supabase 数据库
用法: python3 send_supabase.py [输入文件路径]  （默认 output/今天的日期_enriched.json）

需要先创建表:
  CREATE TABLE IF NOT EXISTS news_chibi (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    bvid text UNIQUE NOT NULL,
    title text,
    summary text,
    category text,
    score integer DEFAULT 0,
    author text,
    url text,
    cover text,
    views text,
    danmaku text,
    like_count text,
    coin text,
    duration text,
    source text,
    collected_at date DEFAULT CURRENT_DATE,
    created_at timestamptz DEFAULT now()
  );
"""
import os
import sys
import json
import urllib.request
import ssl
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
SUPABASE_URL = _env.get("SUPABASE_URL", "")
SUPABASE_KEY = _env.get("SUPABASE_KEY", "")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

OUTPUT_DIR = Path(__file__).parent / "output"


def supabase_request(method: str, path: str, data: dict = None) -> dict:
    """发送请求到 Supabase REST API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 未配置 SUPABASE_URL 或 SUPABASE_KEY")
        return None
    
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    payload = json.dumps(data).encode() if data else None
    
    req = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",  # 只返回最小数据，节省带宽
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            resp_body = resp.read()
            if resp_body:
                return json.loads(resp_body)
            return {"status": resp.status}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"  ❌ Supabase HTTP {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Supabase 错误: {str(e)[:200]}")
        return None


def check_table_exists() -> bool:
    """检查 news_chibi 表是否存在"""
    result = supabase_request("GET", "news_chibi?limit=0")
    return result is not None


def ensure_table():
    """如果表不存在，尝试创建（需要 service_role key）"""
    if check_table_exists():
        return True
    
    print("⚠️  表 news_chibi 不存在，尝试创建...")
    # 注意：创建表需要 service_role key，anon key 可能没有权限
    # 这里只给出 SQL 提示
    sql = """
    CREATE TABLE IF NOT EXISTS news_chibi (
        id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
        bvid text UNIQUE NOT NULL,
        title text,
        summary text,
        category text,
        score integer DEFAULT 0,
        author text,
        url text,
        cover text,
        views text,
        danmaku text,
        like_count text,
        coin text,
        duration text,
        source text,
        collected_at date DEFAULT CURRENT_DATE,
        created_at timestamptz DEFAULT now()
    );
    """
    print("请在 Supabase SQL Editor 中执行以下 SQL：")
    print(sql)
    return False


def upsert_items(items: list) -> bool:
    """批量 upsert 数据到 Supabase"""
    if not items:
        print("⚠️  没有数据需要写入")
        return False
    
    # 准备数据
    today = datetime.now().strftime("%Y-%m-%d")
    records = []
    for item in items:
        bvid = item.get("bvid", "")
        if not bvid:
            continue
        records.append({
            "bvid": bvid,
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "category": item.get("category", "其他"),
            "score": item.get("score", 0),
            "author": item.get("author", ""),
            "url": item.get("url", f"https://www.bilibili.com/video/{bvid}"),
            "cover": item.get("cover", ""),
            "views": item.get("views", ""),
            "danmaku": item.get("danmaku", ""),
            "like_count": item.get("like", ""),
            "coin": item.get("coin", ""),
            "duration": item.get("duration", ""),
            "source": item.get("source", "B站"),
            "collected_at": today,
        })
    
    if not records:
        print("⚠️  没有有效记录")
        return False
    
    # 使用 upsert（ON CONFLICT bvid DO UPDATE）
    result = supabase_request(
        "POST",
        "news_chibi?on_conflict=bvid&columns=bvid,title,summary,category,score,author,url,cover,views,danmaku,like_count,coin,duration,source,collected_at",
        records
    )
    
    if result is not None:
        print(f"✅ 成功写入 {len(records)} 条到 Supabase")
        return True
    return False


def query_recent(limit: int = 10) -> list:
    """查询最近的数据"""
    result = supabase_request(
        "GET",
        f"news_chibi?order=score.desc&limit={limit}"
    )
    return result if result else []


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    input_file = sys.argv[1] if len(sys.argv) > 1 else str(OUTPUT_DIR / f"{today}_enriched.json")
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 找不到输入文件: {input_path}")
        return
    
    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    
    # 只写入评分 > 0 的
    qualified = [i for i in items if i.get("score", 0) > 0]
    print(f"📥 读取 {len(items)} 条，评分>0: {len(qualified)} 条")
    
    if not qualified:
        print("⚠️  没有合格数据，跳过")
        return
    
    # 检查配置
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ 未配置 SUPABASE_URL 或 SUPABASE_KEY")
        print("   请在 .env 中添加:")
        print("   SUPABASE_URL=https://your-project.supabase.co")
        print("   SUPABASE_KEY=your-anon-or-service-role-key")
        return
    
    # 检查表
    if not ensure_table():
        print("❌ 表不存在，请先创建")
        return
    
    # 写入数据
    print(f"📤 写入 Supabase...")
    success = upsert_items(qualified)
    
    if success:
        # 查询验证
        recent = query_recent(5)
        if recent:
            print(f"\n📊 Supabase 最新数据（前5条）:")
            for item in recent:
                print(f"   [{item.get('score', 0)}] {item.get('summary', '')[:40]}")


if __name__ == "__main__":
    main()
