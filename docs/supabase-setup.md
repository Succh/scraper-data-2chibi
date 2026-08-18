# Supabase 第二存储后端配置

## 概述

Supabase 作为 Notion 的补充存储后端，提供：
- 云端 PostgreSQL 数据库
- RESTful API 直接访问
- 免费额度：500MB 数据库 + 2GB 带宽
- 支持复杂查询和数据分析

## 架构

```
采集 → 富化 → Notion（主）
              ↘ Supabase（备）
```

## 配置步骤

### 1. 创建 Supabase 项目

1. 访问 https://supabase.com 并登录
2. 点击 "New project"
3. 填写项目名称（如 `2chibi-news`）
4. 设置数据库密码（记住它）
5. 选择区域（推荐 Singapore 或 Tokyo，离 B 站用户近）
6. 等待项目创建完成（约 2 分钟）

### 2. 创建数据表

在 Supabase 左侧菜单选择 **SQL Editor**，粘贴并执行：

```sql
-- 创建二次元趣闻表
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

-- 创建索引（加速查询）
CREATE INDEX IF NOT EXISTS idx_news_chibi_score ON news_chibi(score DESC);
CREATE INDEX IF NOT EXISTS idx_news_chibi_category ON news_chibi(category);
CREATE INDEX IF NOT EXISTS idx_news_chibi_collected_at ON news_chibi(collected_at DESC);

-- 启用 Row Level Security（可选，公开读取）
ALTER TABLE news_chibi ENABLE ROW LEVEL SECURITY;

-- 允许匿名读取
CREATE POLICY "Allow anonymous read" ON news_chibi
    FOR SELECT TO anon USING (true);

-- 允许 service_role 完全控制
CREATE POLICY "Allow service_role full access" ON news_chibi
    FOR ALL TO service_role USING (true);
```

### 3. 获取 API Key

1. 左侧菜单 → **Settings** → **API**
2. 复制 **Project URL** → 填入 `.env` 的 `SUPABASE_URL`
3. 复制 **service_role key** → 填入 `.env` 的 `SUPABASE_KEY`

⚠️ **重要**：使用 `service_role key` 而不是 `anon key`，因为需要 upsert 权限。

### 4. 配置 .env

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIs...（service_role key）
```

### 5. 测试写入

```bash
# 写入今天的富化数据到 Supabase
python3 send_supabase.py

# 指定文件
python3 send_supabase.py output/2026-08-18_enriched.json
```

## 数据表结构

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 主键，自动生成 |
| bvid | text | B站视频ID，唯一索引 |
| title | text | 视频标题 |
| summary | text | AI 生成的趣闻摘要 |
| category | text | 分类（日本文化/声优/游戏等） |
| score | integer | AI 评分（0-100） |
| author | text | UP主 |
| url | text | B站链接 |
| cover | text | 封面图URL |
| views | text | 播放量 |
| danmaku | text | 弹幕数 |
| like_count | text | 点赞数 |
| coin | text | 投币数 |
| duration | text | 视频时长 |
| source | text | 来源（B站） |
| collected_at | date | 采集日期 |
| created_at | timestamptz | 记录创建时间 |

## 常用查询示例

```sql
-- 今日精选（评分≥70）
SELECT * FROM news_chibi
WHERE collected_at = CURRENT_DATE AND score >= 70
ORDER BY score DESC;

-- 分类统计
SELECT category, COUNT(*) as cnt, AVG(score) as avg_score
FROM news_chibi
WHERE collected_at >= CURRENT_DATE - 7
GROUP BY category
ORDER BY cnt DESC;

-- 最近7天每日采集数
SELECT collected_at, COUNT(*) as cnt
FROM news_chibi
WHERE collected_at >= CURRENT_DATE - 7
GROUP BY collected_at
ORDER BY collected_at;
```

## 与 GitHub Actions 集成

在 `.github/workflows/daily-crawl.yml` 中添加 Supabase Secrets：

```yaml
- name: 写入 Supabase
  working-directory: scraper-data-2chibi
  run: python3 send_supabase.py
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
```

在 GitHub 仓库 Secrets 中添加 `SUPABASE_URL` 和 `SUPABASE_KEY`。

## 免费额度

| 资源 | 免费额度 |
|---|---|
| 数据库 | 500MB |
| 带宽 | 2GB/月 |
| API 请求 | 无限制（合理使用时） |
| 存储 | 1GB（用于图片等） |

## 故障排查

- **403 Forbidden**：检查 RLS 策略是否正确配置
- **404 Not Found**：检查 SUPABASE_URL 是否正确（末尾不要加 `/`）
- **409 Conflict**：bvid 重复，正常（upsert 会更新）
- **表不存在**：确认已在 SQL Editor 中执行建表语句
