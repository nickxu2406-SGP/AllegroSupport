# AllegroSupport 邮件知识库 - 原型验证报告

**生成时间**: 2026-04-06 17:55  
**项目路径**: `allegrosupport-kb/`

---

## 一、数据采集结果

### 邮件统计
- **总邮件数**: 77 封（最近 7 天）
- **IT 回复**: 15 封（Joanne Ding）
- **用户提问**: 62 封

### 邮件来源
- **收件箱**: 包含 `#CUL Allegro Support` 或 `allegrosupport@culines.com` 的邮件
- **时间范围**: 2026-03-30 至 2026-04-06
- **发送者识别**: 
  - IT 人员：Joanne Ding/CUL-CN/IT
  - 用户：其他所有发件人

---

## 二、问答对提取结果

### 提取统计
- **成功提取**: 2 个问答对
- **分类结果**: 全部为"其他"类别

### 示例问答对

#### 问答对 #1
**主题**: Storage Waiver Request // SHENGTANG 2606W  
**提问人**: Colleeh Zhou/CUL-CN/AEM Trade (04-03 17:27)  
**问题内容**:
```
Dear,
    Please create a new one as below, now is wrong, thanks.
```

**回复人**: Joanne Ding/CUL-CN/IT (04-06 15:35)  
**答案内容**:
```
Dear Randa,

Please follow Colleeh's advise to input 'Add 1 day' but not 'Total 1 day'. Thanks!
```

#### 问答对 #2
**主题**: Storage Waiver Request // SHENGTANG 2606W  
**提问人**: Colleeh Zhou/CUL-CN/AEM Trade (04-03 17:27)  
**问题内容**:
```
Dear,
    Please create a new one as below, now is wrong, thanks.
```

**回复人**: Joanne Ding/CUL-CN/IT (04-06 16:18)  
**答案内容**:
```
Dear Randa,

Please do not input ratio 100% when you has inputted total 1 day. Tks~
```

---

## 三、技术方案验证

### 已验证功能
1. **邮件采集** ✅
   - 成功从 Outlook 读取邮件
   - 正确识别 allegrosupport 邮箱
   - 区分 IT 回复和用户提问

2. **线程识别** ⚠️
   - 基于主题分组
   - 按时间排序
   - **问题**: 算法较严格，提取率低（2/15 = 13%）

3. **问答对提取** ⚠️
   - 基本功能可用
   - 需要优化匹配算法

4. **问题分类** ⚠️
   - 关键词匹配
   - 需要扩充关键词库

---

## 四、改进方向

### 短期优化（1-2 周）
1. **改进线程识别算法**
   - 解析邮件正文中的"发件人"和"发送时间"
   - 精确匹配 IT 回复对应的原始问题
   - 预期提取率提升至 80%+

2. **扩充问题分类关键词**
   ```python
   CATEGORIES = {
       "订舱操作": ["订舱", "booking", "SO", "slot", ...],
       "提单操作": ["提单", "BL", "bill of lading", "draft", ...],
       "费用相关": ["费用", "charge", "fee", "invoice", ...],
       "系统问题": ["系统", "system", "error", "bug", ...],
       # ... 更多分类
   }
   ```

3. **数据清洗**
   - 移除邮件签名
   - 移除历史引用
   - 提取核心问题内容

### 中期建设（1-2 月）
1. **接入向量数据库**
   - 使用 ChromaDB 或腾讯云向量数据库
   - 实现语义检索
   - 支持相似问题匹配

2. **接入大模型**
   - 使用 DeepSeek 或其他国产模型
   - 智能生成答案
   - 润色回复内容

3. **Web 界面**
   - 查询知识库
   - 搜索历史问答
   - 管理员后台

### 长期规划（3-6 月）
1. **自动回复系统**
   - 新邮件自动分类
   - 匹配历史答案
   - 生成回复建议

2. **团队协作**
   - 多人标注问答对
   - 质量审核流程
   - 知识库版本管理

3. **分析报表**
   - 常见问题统计
   - 团队绩效分析
   - 用户满意度调查

---

## 五、下一步行动

### 立即可做
1. **扩大数据范围**
   ```bash
   # 修改脚本，读取最近 30 天邮件
   start_date = datetime.now() - timedelta(days=30)
   ```

2. **手动标注问答对**
   - 导出 IT 回复邮件
   - 人工标注问题和答案
   - 建立种子数据集

3. **测试语义检索**
   - 使用 2 个问答对作为测试数据
   - 演示向量检索效果

### 需要资源
1. **开发环境**
   - Python 3.11+ ✅
   - PostgreSQL + pgvector（向量数据库）
   - DeepSeek API 密钥

2. **权限申请**
   - Microsoft Graph API 权限（读取共享邮箱）
   - Outlook API 权限

3. **人员支持**
   - IT 部门：API 权限申请
   - Allegro 支持团队：标注问答对

---

## 六、项目文件结构

```
allegrosupport-kb/
├── README.md                 # 系统设计文档
├── PROTOTYPE_REPORT.md       # 原型验证报告
├── database/
│   └── schema.sql            # 数据库设计
├── scripts/
│   ├── email_collector.py    # 邮件采集脚本（Graph API）
│   └── prototype_demo.py     # 原型演示脚本
└── data/
    └── qa_pairs.json         # 提取的问答对
```

临时脚本：
- `_fetch_allegro_emails.py` - 读取 Outlook 邮件
- `_analyze_allegro_emails.py` - 分析邮件提取问答对
- `_allegro_emails.json` - 邮件原始数据

---

## 七、成本估算

### 开发成本
- **人力**: 1 人月（原型开发）
- **服务器**: 腾讯云 CVM（2核4G）约 ¥100/月
- **向量数据库**: 腾讯云向量数据库约 ¥200/月
- **大模型**: DeepSeek API 约 ¥50/月（初期）

### 总计
- **初期开发**: ¥20,000 - ¥30,000
- **月度运维**: ¥350 - ¥500

---

## 八、联系方式

**项目负责人**: Nick Xu  
**技术支持**: WorkBuddy AI Agent  
**文档更新**: 2026-04-06
