# AllegroSupport KB

> 航运操作系统常见问题知识库 - 无需部署，打开即用

**在线访问**：https://nickxu2406-sgp.github.io/AllegroSupport/

---

## Features

- **全前端实现** - 纯 HTML + JS，无需服务器，打开即用
- **71 条问答对** - 覆盖 90 天真实 IT 支持邮件
- **分类检索** - 订舱 / 报关 / 提单 / 数据修改 / 系统问题 / 其他
- **订舱优先模式** - 命中航运关键词时对订舱类 x1.5 加权
- **关键词 + N-gram 搜索** - 中英文混合检索，无需向量数据库

---

## Quick Start

**直接访问**：https://nickxu2406-sgp.github.io/AllegroSupport/

**本地运行**：

```bash
# 方法一：直接用浏览器打开
open index.html

# 方法二：用 Python 简单服务器
python -m http.server 8000
# 然后访问 http://localhost:8000
```

---

## Project Structure

```
allegrosupport-kb/
├── index.html              # GitHub Pages 主页（内嵌 71 条问答数据）
├── README.md               # 本文档
├── requirements.txt        # Python 依赖（本地开发用）
├── .github/workflows/deploy.yml  # GitHub Actions 自动部署
├── data/
│   ├── qa_pairs_public.json  # 公开版问答数据（JSON）
│   └── README.md           # 数据说明
└── scripts/
    ├── web_app.py          # FastAPI Web 界面（本地开发版）
    ├── stats_report.py     # 统计分析报告
    ├── vector_store.py     # 向量检索（可选）
    ├── demo_search.py      # 命令行搜索
    └── email_collector.py  # Graph API 邮件采集
```

---

## Data Statistics (90 Days)

| Metric | Value |
|--------|-------|
| Q&A Pairs | 71 |
| Booking Operations | 27 (38%) |
| B/L Operations | 12 (17%) |
| Customs Operations | 11 (15%) |
| Other | 21 (30%) |

---

## Architecture

```
Email History (Outlook)
        |
        v
_email_collector.py_
        |
        v
_qa_pairs.json_ (raw)
        |
        v
_generate_public.py_ -> qa_pairs_public.json
        |
        v
index.html (embedded JSON + JS search)
        |
        v
GitHub Pages -> https://nickxu2406-sgp.github.io/AllegroSupport/
```

---

## Deployment

GitHub Pages 自动部署已配置（`.github/workflows/deploy.yml`）。

每次向 `master` 分支推送后，自动部署到 GitHub Pages。

如需自定义域名：在仓库 Settings > Pages > Custom domain 中配置。

---

## Tech Stack

- **Search**: Keyword + N-gram (pure JS, no backend)
- **UI**: Vanilla HTML/CSS/JS (no build step)
- **Deployment**: GitHub Pages (free, global CDN)

---

## License

MIT License


---

## Features

- **邮件智能解析** - 自动识别 IT 回复与用户提问，提取高质量问答对
- **分类检索** - 支持按订舱/报关/提单等业务场景分类搜索
- **订舱优先模式** - 对航运核心业务（订舱操作）加权，优先返回最相关答案
- **Web 知识库** - 轻量 FastAPI Web 界面，开箱即用
- **训练数据导出** - 生成可直接用于 LLM 微调的指令数据集

---

## Project Structure

```
allegrosupport-kb/
├── README.md              # 项目文档
├── requirements.txt       # Python 依赖
├── config/                # 配置文件
├── data/                  # 问答对数据
│   ├── qa_pairs.json          # 基础问答对
│   ├── booking_qa_pairs.json   # 订舱操作专集（27条）
│   ├── booking_training_data.json  # 订舱微调数据（27条）
│   └── booking_system_prompt.txt   # 订舱系统提示词
├── scripts/
│   ├── web_app.py         # Web 知识库界面（FastAPI）
│   ├── stats_report.py    # 统计分析报告
│   ├── vector_store.py    # 向量检索（ChromaDB）
│   ├── demo_search.py     # 命令行搜索演示
│   └── email_collector.py # Graph API 邮件采集
└── database/
    └── schema.sql         # PostgreSQL Schema
```

---

## Quick Start

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Web 知识库

```bash
cd scripts
python web_app.py
```

访问 http://localhost:8000

### 3. 命令行搜索演示

```bash
python scripts/demo_search.py
```

---

## Data Format

问答对格式（JSON）：

```json
{
  "id": "booking_001",
  "category": "订舱操作",
  "subject": "SO Status Update Request",
  "question": {
    "sender": "user@example.com",
    "text": "Hi, could you please update the SO status to confirmed?",
    "timestamp": "2026-01-15T10:30:00Z"
  },
  "answer": {
    "responder": "support@example.com",
    "text": "Done. SO confirmed and slot reserved.",
    "timestamp": "2026-01-15T11:05:00Z"
  },
  "has_attachment": true,
  "keywords": ["booking", "SO", "update", "confirmed"]
}
```

---

## Statistics (90 Days)

| Metric | Value |
|--------|-------|
| Total Q&A Pairs | 71 |
| Booking Operations | 27 (38%) |
| B/L Operations | 12 (17%) |
| Customs Operations | 11 (15%) |
| Top Responder | Kieran Ji (50.7%) |
| Active Questioners | 37 |

---

## Architecture

```
Outlook/Graph API
       │
       ▼
_email_collector.py_
       │
       ▼
_qa_pairs.json_ (raw Q&A pairs)
       │
       ▼
web_app.py / demo_search.py
  (keyword + n-gram search)
       │
       ▼
[Web UI / API Response]
```

---

## Tech Stack

- **Search**: Keyword matching + n-gram indexing (no external vector DB required)
- **Web**: FastAPI + Uvicorn + Jinja2
- **Optional**: ChromaDB + Sentence-Transformers for semantic search
- **Email**: Microsoft Graph API / win32com (Outlook)

---

## Deployment

### Local

```bash
pip install -r requirements.txt
cd scripts
python web_app.py --host 0.0.0.0 --port 8000
```

### Docker (optional)

```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "scripts/web_app.py"]
```

---

## License

MIT License

---

## Contributing

Issues and Pull Requests are welcome! Please see the data format section for contribution guidelines.
