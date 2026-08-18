# GitHub Actions 定时采集配置

## 概述

本项目使用 GitHub Actions 实现每日自动采集二次元趣闻，无需服务器，100% 免费。

## 工作流程

```
每天 08:00 (北京时间)
    │
    ▼
┌─────────────────────┐
│  GitHub Actions     │
│  检出代码            │
│  安装 Python 3.11   │
│  安装依赖            │
│  配置 .env (Secrets) │
│  运行 run_pipeline   │
│  提交结果到仓库      │
└─────────────────────┘
```

## 配置步骤

### 1. 推送代码到 GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/scraper-data-2chibi.git
git push -u origin master
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库页面：**Settings → Secrets and variables → Actions → New repository secret**

添加以下 3 个 Secret：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `NOTION_TOKEN` | Notion Integration Token | `ntn_242172...` |
| `NOTION_DATABASE_ID` | Notion 数据库 ID | `3c05a375-9092-8006-aad0-fd6a93507540` |

### 3. 启用 Actions

在 GitHub 仓库页面：**Actions → 点击 "I understand my workflows, go ahead and enable them"**

### 4. 手动测试

在 Actions 页面选择 "二次元趣闻每日采集" → **Run workflow**

## 定时设置

当前设置：每天北京时间 **08:00** 执行（UTC 00:00）

修改定时：编辑 `.github/workflows/daily-crawl.yml` 中的 cron 表达式：

```yaml
- cron: '0 0 * * *'   # 每天 00:00 UTC = 北京 08:00
- cron: '0 2 * * *'   # 每天 02:00 UTC = 北京 10:00
- cron: '0 0 * * 1'   # 每周一 00:00 UTC
```

## 输出产物

每次运行后：
- `output/{日期}.json` - 原始采集数据
- `output/{日期}_enriched.json` - AI 富化后数据
- `output/{日期}_enriched.md` - Markdown 日报
- `index.html` - 可视化页面（自动更新）

产物会自动提交到仓库，也可在 Actions 页面下载（保留 7 天）。

## 注意事项

1. **GitHub Actions 免费额度**：每月 2000 分钟（公共仓库无限）
2. **Gemini API 免费额度**：每分钟 15 次请求，每天 1500 次
3. **Notion API 限制**：每秒 3 次请求
4. **B站 API 限制**：无官方限制，但建议不要过于频繁

## 故障排查

- 查看运行日志：Actions → 选择一次运行 → 查看各步骤日志
- 常见错误：
  - `GEMINI_API_KEY 无效` → 检查 Secret 是否正确
  - `Notion 写入失败` → 检查数据库是否已分享给 Integration
  - `B站 API 超时` → 网络问题，会自动重试
