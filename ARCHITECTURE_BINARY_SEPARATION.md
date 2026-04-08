# AllegroSupport KB — 二元分离架构设计

> 核心原则：raw 层保留原始邮件的完整信息与可追溯性；wiki 层提供 AI 高效索引的结构化知识。

---

## 一、为什么需要二元分离

| 问题 | 原因 | 后果 |
|------|------|------|
| `qa_pairs.json` 中 question/answer 和原始邮件混在一起 | 早期为快速上线做的平铺结构 | 原始邮件上下文丢失，QA 质量无法回溯审核 |
| 无 keywords / confidence_score 字段 | JSON 结构设计时未考虑 | 搜索依赖全文匹配，无法区分高频/冷门问题 |
| JSON 是单一文件，无原子性 | 没做文件级拆分 | 并发编辑冲突，无法增量同步 |
| 无法区分"原始问题"和"处理后的问题" | 缺乏 raw 层抽象 | AI 生成的摘要无法对照原始邮件核实 |

二元分离彻底解决这四个问题：raw 层是**不可篡改的原始记录**，wiki 层是**可任意编辑的结构化知识**。

---

## 二、目录结构

```
allegrosupport-kb/
│
├── raw/                              # 【只读】原始素材库
│   ├── emails/                       # 原始邮件（按 Graph API ID）
│   │   ├── AAMkADxxx...json          # 一封邮件 = 一个文件
│   │   ├── AAMkADyyy...json          # 文件名 = Graph API 邮件 ID
│   │   └── ...
│   ├── threads/                      # 邮件线程（按 conversation_id）
│   │   └── {conversation_id}.json    # 合并整个会话链
│   └── index.json                    # 全局索引（email_id → 文件路径）
│
├── wiki/                             # 【可读写】结构化知识库
│   ├── qa/                           # QA 对（每条一个 .json 文件）
│   │   ├── qa_001.json
│   │   ├── qa_002.json
│   │   └── ...
│   ├── categories/                   # 按分类组织的软链接索引
│   │   ├── 订舱操作/
│   │   │   ├── index.json            # 本分类 QA 列表
│   │   │   └── qa_001.json           # 引用 wiki/qa/ 下的实体
│   │   ├── 报关操作/
│   │   ├── 提单操作/
│   │   ├── 系统问题/
│   │   └── ...
│   ├── tags/                         # 按标签组织的索引
│   │   ├── 高频问题/
│   │   │   └── index.json
│   │   ├── 待审核/
│   │   └── ...
│   ├── index.json                    # 全量 QA 索引（ID → path）
│   └── search_index.json             # 预构建搜索索引（AI 直接读取）
│
├── scripts/                          # 转换 & 同步脚本
│   ├── email_collector.py            # Graph API → raw/emails/
│   ├── thread_builder.py             # raw/emails → raw/threads/
│   ├── qa_extractor.py               # raw/threads → wiki/qa/
│   ├── search_indexer.py             # wiki/qa → wiki/search_index.json
│   ├── migrate_flat_json.py          # 旧 qa_pairs.json → raw/ + wiki/
│   └── sync_stats.py                 # 统计 & 健康检查
│
├── data/                             # 【遗留，迁移完成后删除】
│   └── qa_pairs.json                 # → 拆分为 raw/ + wiki/
│
└── database/                         # 【可选】PostgreSQL 向量库
    ├── schema.sql
    └── ...                           # wiki/ 作为 PostgreSQL 的扁平缓存层
```

---

## 三、raw/ 层设计

### 3.1 原始邮件文件

**路径**：`raw/emails/{YYYY}/{MM}/{graph_email_id}.json`

**文件命名规则**：
- 使用 Graph API 返回的 `id` 字段作为文件名（唯一不变）
- 不重命名、不移动、不合并
- 目录按 `YYYY/MM` 自动归档（如 `raw/emails/2026/04/`）

**文件内容**：Graph API 返回的完整 JSON，不做任何裁剪。

```json
{
  "id": "AAMkADg5...",
  "conversationId": "AAQkADg5...",
  "internetMessageId": "<xxxxxxxx@example.com>",
  "subject": "Update the Route detail related to AEJEAT01 in Allegro",
  "sender": {
    "emailAddress": {
      "name": "Siraj - National Shipping",
      "address": "siraj@nationaldubai.ae"
    }
  },
  "toRecipients": [...],
  "ccRecipients": [...],
  "receivedDateTime": "2026-03-31T08:51:00Z",
  "sentDateTime": "2026-03-31T08:51:00Z",
  "body": {
    "contentType": "text",
    "content": "Dear Sir,\n\n..."
  },
  "hasAttachments": true,
  "importance": "normal",
  "inReplyTo": "...",
  "references": "...",
  "webLink": "https://outlook.office365.com/..."
}
```

### 3.2 邮件线程文件

**路径**：`raw/threads/{conversation_id}.json`

**合并规则**：同一 `conversationId` 下的所有邮件按时间排序合并。

```json
{
  "conversation_id": "AAQkADg5...",
  "subject": "Update the Route detail related to AEJEAT01 in Allegro",
  "emails": [
    { "$ref": "../emails/2026/03/AAMkADxxx.json" },
    { "$ref": "../emails/2026/04/AAMkADyyy.json" }
  ],
  "participants": [
    { "name": "Siraj", "email": "siraj@nationaldubai.ae", "role": "external" },
    { "name": "Kieran Ji", "email": "kieranji@culines.com", "role": "support" }
  ],
  "first_email_at": "2026-03-31T08:51:00Z",
  "last_email_at": "2026-04-07T04:15:00Z",
  "email_count": 2
}
```

### 3.3 全局索引文件

**路径**：`raw/index.json`

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T11:30:00Z",
  "total_emails": 1523,
  "total_threads": 489,
  "emails_by_month": {
    "2026-04": { "count": 87, "emails": ["AAMkADxxx", "AAMkADyyy", ...] },
    "2026-03": { "count": 134, "emails": [...] }
  },
  "by_id": {
    "AAMkADxxx": { "path": "emails/2026/03/AAMkADxxx.json", "thread_id": "AAQkADg5..." },
    "AAMkADyyy": { "path": "emails/2026/04/AAMkADyyy.json", "thread_id": "AAQkADg5..." }
  }
}
```

### 3.4 发件人角色判定规则

**核心原则**：通过发件人邮箱判断邮件角色，不新建专门的问答邮箱。

| 角色 | 判定规则 | 处理方式 |
|------|----------|----------|
| **support（回答者）** | 发件人 ∈ IT 同事邮箱白名单 | 邮件归入 `answer` |
| **external（提问者）** | 发件人 ∉ IT 同事邮箱白名单 | 邮件归入 `question` |

**IT 同事邮箱白名单**（从现有数据提取）：

| 姓名 | 邮箱 | 回答数量 |
|------|------|----------|
| Kieran Ji | kieranji@culines.com | 36 条 |
| Joanne Ding | joanneding@culines.com | 26 条 |
| Catherine Kang | catherinekang@culines.com | 7 条 |

**实时判定逻辑**（email_collector.py）：

```python
SUPPORT_SENDERS = {
    'kieranji@culines.com',
    'joanneding@culines.com',
    'catherinekang@culines.com'
}

def get_sender_role(sender_email):
    return 'support' if sender_email.lower() in SUPPORT_SENDERS else 'external'
```

**优势**：
- 无需新建邮箱，直接复用现有 `allegrosupport@culines.com` 共享邮箱
- 通过发件人自动区分问答角色
- 白名单可在配置文件中动态更新

### 3.5 raw/ 层的核心约束

| 约束 | 说明 |
|------|------|
| **不可篡改** | raw/ 下所有文件写入后禁止修改。若 Graph API 数据有误，修正值记录在 wiki/ 的 `raw_corrections` 字段 |
| **仅追加** | 新邮件追加到 `raw/emails/YYYY/MM/`，不修改历史文件 |
| **元数据溯源** | 每封邮件文件保留 Graph API 返回的完整原始字段，包括 `webLink`（可跳转原始邮件） |
| **保留删除记录** | 被 Graph API 标记为 deleted 的邮件，保留 `deleted_email_{id}.meta.json`（元数据墓碑） |

---

## 四、wiki/ 层设计

### 4.1 QA 实体文件

**路径**：`wiki/qa/{qa_id}.json`

```json
{
  "id": "qa_001",
  "version": 1,

  "question": {
    "text": "Dear Sir, we are encountering an issue while updating the VD move...",
    "original_email_id": "AAMkADxxx",
    "sender_name": "Siraj - National Shipping",
    "sender_email": "siraj@nationaldubai.ae",
    "sent_at": "2026-03-31T08:51:00Z",
    "summary": "在 Fujairah Terminal 卸船后更新 VD move 时报错：Event Yard 与 Login Office 不匹配",
    "keywords": ["VD move", "Fujairah", "yard", "event yard"]
  },

  "answer": {
    "text": "Dear Siraj, Please try again, should be in order now, thanks!",
    "original_email_id": "AAMkADyyy",
    "responder_name": "Kieran Ji / 季胤喆",
    "responder_email": "kieranji@culines.com",
    "sent_at": "2026-04-07T04:15:00Z",
    "summary": "问题已修复，请重试",
    "keywords": ["VD move", "fixed"]
  },

  "thread": {
    "id": "AAQkADg5...",
    "path": "../raw/threads/AAQkADg5.json",
    "web_link": "https://outlook.office365.com/...（指向原始线程）"
  },

  "classification": {
    "category": "订舱操作",
    "subcategory": "VD 移动",
    "related_system": "Allegro",
    "related_module": "Vessel Discharge",
    "tags": ["高频问题", "场地映射"]
  },

  "quality": {
    "confidence_score": 0.92,
    "is_verified": true,
    "verified_by": "nickxu@culines.com",
    "verified_at": "2026-04-07T10:00:00Z",
    "helpful_count": 5,
    "escalation_count": 0
  },

  "source": {
    "extracted_from": "raw/threads/AAQkADg5.json",
    "extracted_at": "2026-04-07T11:30:00Z",
    "extracted_by": "qa_extractor.py v1.0"
  },

  "history": [
    {
      "action": "create",
      "at": "2026-04-07T11:30:00Z",
      "by": "qa_extractor.py"
    },
    {
      "action": "verify",
      "at": "2026-04-07T10:00:00Z",
      "by": "nickxu@culines.com",
      "changes": { "is_verified": true, "tags": ["高频问题"] }
    }
  ]
}
```

### 4.2 分类索引

**路径**：`wiki/categories/{分类名}/index.json`

```json
{
  "category": "订舱操作",
  "total": 27,
  "qa_ids": ["qa_001", "qa_003", "qa_007", ...],
  "last_updated": "2026-04-07T11:30:00Z"
}
```

### 4.3 搜索索引（AI 直读）

**路径**：`wiki/search_index.json`

**用途**：AI Agent 直接读取此文件进行检索，无需解析分散的 qa/*.json。

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T11:30:00Z",
  "total": 71,
  "records": [
    {
      "id": "qa_001",
      "path": "qa/qa_001.json",
      "category": "订舱操作",
      "tags": ["高频问题", "场地映射"],
      "question_keywords": ["VD move", "Fujairah", "yard", "event yard", "VD", "yard mapping"],
      "answer_summary": "问题已修复，请重试",
      "confidence": 0.92,
      "is_verified": true
    }
  ]
}
```

**搜索流程（改造后）**：

```
用户查询
  ↓
读取 wiki/search_index.json（单文件，无需遍历）
  ↓
TF-IDF / BM25 评分
  ↓
命中 qa_id → 读取 wiki/qa/{id}.json（获取完整信息）
  ↓
通过 thread.path → raw/threads/{id}.json（回溯原始邮件）
```

---

## 五、数据流向

```
Graph API
    │
    ▼
email_collector.py          【写入】raw/
    │                        raw/emails/YYYY/MM/{id}.json
    │                        raw/index.json
    ▼
thread_builder.py           【写入】raw/
    │                        raw/threads/{conversation_id}.json
    ▼
qa_extractor.py             【写入】wiki/
    │                        wiki/qa/{qa_id}.json
    │                        wiki/categories/{cat}/index.json
    ▼
search_indexer.py           【写入】wiki/
                             wiki/search_index.json
    │
    ▼
前端搜索 UI / AI Agent
  (读取 wiki/search_index.json + wiki/qa/{id}.json)
  (通过 thread.path 回溯 raw/threads/{id}.json → 原始邮件)
```

---

## 六、与旧架构的对比

| 维度 | 旧架构（qa_pairs.json） | 新架构（raw/wiki） |
|------|------------------------|---------------------|
| 原始邮件 | 嵌入 JSON 字符串（已脱敏） | 完整保留，可跳转原始 |
| QA 可编辑性 | 整文件读写，无法增量 | 每条独立文件，原子更新 |
| 搜索性能 | 需解析 139KB JSON | 预构建索引（AI 直读） |
| 回溯能力 | 无 | `thread.path` → 原始邮件 |
| 标签体系 | 无 | tags / subcategory / keywords |
| 质量评分 | 无 | confidence_score / is_verified |
| 并发安全 | 文件锁 | 每条独立文件，无冲突 |
| Git 友好 | 每次改 139KB diff 难读 | 每条独立 commit，易 review |
| AI 追溯 | 答案来源不明 | `source.extracted_from` 明确记录 |

---

## 七、迁移计划

### 第一阶段：存量数据迁移（一次性）
```
scripts/migrate_flat_json.py
  输入：data/qa_pairs.json（71 条）
  输出：
    - raw/emails/（虚拟，按现有数据重建 metadata）
    - raw/threads/
    - wiki/qa/{qa_id}.json × 71
    - wiki/search_index.json
```

### 第二阶段：Graph API 接入（持续）
```
email_collector.py（增量拉取）
  → raw/emails/YYYY/MM/{id}.json
  → raw/index.json
  ↓
qa_extractor.py（批量处理未抽取的 threads）
  → wiki/qa/{new_id}.json
  ↓
search_indexer.py
  → wiki/search_index.json（增量更新）
```

### 第三阶段：前端适配
```
index.html（改造）
  旧：内嵌 qa_pairs_public.json（96KB）
  新：fetch wiki/search_index.json + wiki/qa/{id}.json
  保留：通过 qa_id → thread_id → raw/threads/ 回溯链接
```

---

## 八、PostgreSQL 向量库定位

二元分离架构与 PostgreSQL 不是竞争关系，而是**互补**：

```
raw/ ← 文件系统（原始素材，不可篡改）
wiki/ ← 文件系统（结构化知识，AI 直读）
PostgreSQL ← 可选（pgvector 向量索引层）

wiki/search_index.json ──→ PostgreSQL qa_pairs 表（embedding 列）
                          ──→ 用于语义相似搜索
                          ──→ wiki/ 作为 PostgreSQL 的只读缓存
```

**结论**：PostgreSQL 向量库是 wiki/ 层的可选加速层，不替代 wiki/ 文件系统存储。
