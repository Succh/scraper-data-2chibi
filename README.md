# 🎬 二次元趣闻采集器

B站自动采集 → Gemini AI 富化评分 → Notion 数据库自动写入

## 快速开始

### 一键运行完整管道
```bash
cd /workspace/scraper-data-2chibi
python3 run_pipeline.py
```

### 分步运行
```bash
python3 run_pipeline.py --scrape      # 仅采集 B站
python3 run_pipeline.py --enrich      # 仅 AI 富化
python3 run_pipeline.py --send        # 仅写入 Notion
python3 run_pipeline.py --dedup-only  # 查看去重报告
```

## 定时自动采集

### Ubuntu crontab（每天凌晨 2 点）
```bash
crontab -e
# 添加:
0 2 * * * cd /workspace/scraper-data-2chibi && bash scripts/cron_daily.sh >> output/cron.log 2>&1
```

### 手动触发
```bash
bash scripts/cron_daily.sh
```

## 去重机制

- 基于 B站 BV 号去重
- 缓存文件: `output/dedup_cache.json`
- 已采集的 BV 号不会被重复写入 Notion
- 初始缓存已从 2026-08-18 的 20 条数据预填充

## 项目结构

```
├── scrape.py           # B站采集 + 富化 + 写入（旧版一体化）
├── enrich.py           # AI 富化（支持命令行参数）
├── send.py             # 写入 Notion（支持命令行参数）
├── run_pipeline.py     # 管道调度器（去重 + 一键运行）
├── verify.py           # 数据验证
├── cleanup2.py         # 清理空内容记录
├── index.html          # 可视化卡片页面
├── scripts/
│   └── cron_daily.sh   # 定时任务脚本
├── output/
│   ├── 2026-08-18.json               # 原始采集
│   ├── 2026-08-18_enriched.json      # 富化数据
│   └── dedup_cache.json              # 去重缓存
└── .env                        # API 密钥配置
```

## 配置

`.env` 文件需要包含：
- `GEMINI_API_KEY` - Gemini API 密钥
- `NOTION_TOKEN` - Notion Integration Token
- `NOTION_DATABASE_ID` - Notion 数据库 ID