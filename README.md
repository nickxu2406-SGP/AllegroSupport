# AllegroSupport KB

> 基于邮件历史的智能航运操作知识库系统

基于真实 IT 支持邮件数据构建的航运操作问答知识库，可快速扩展为 AI 自动回复助手。适用于货代、船公司、物流公司等航运操作团队的知识沉淀与智能辅助。

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
