#!/bin/bash
# 二次元趣闻采集 - 每日定时任务
# 用法: 加入 crontab 每天凌晨2点执行
#   0 2 * * * cd /workspace/scraper-data-2chibi && bash scripts/cron_daily.sh >> output/cron.log 2>&1

set -e

PROJECT_DIR="/workspace/scraper-data-2chibi"
cd "$PROJECT_DIR"

echo "=========================================="
echo "🎬 二次元趣闻采集 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 运行完整管道（采集→富化→去重→写入 Notion）
python3 run_pipeline.py

echo ""
echo "=========================================="
echo "✅ 完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="