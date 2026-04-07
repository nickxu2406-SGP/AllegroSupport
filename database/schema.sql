-- AllegroSupport 知识库数据库 Schema
-- PostgreSQL 15+

-- ============================================
-- 1. 邮件原始数据表
-- ============================================
CREATE TABLE emails (
    id VARCHAR(255) PRIMARY KEY,  -- Microsoft Graph API 邮件 ID
    conversation_id VARCHAR(255) NOT NULL,  -- 会话线程 ID
    internet_message_id VARCHAR(255),  -- Message-ID 头
    
    -- 基本信息
    subject TEXT,
    sender_email VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255),
    recipients JSONB,  -- ["email1", "email2"]
    cc JSONB,  -- ["email1", "email2"]
    
    -- 时间
    received_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    
    -- 内容
    body_text TEXT,
    body_html TEXT,
    
    -- 线程关系
    in_reply_to VARCHAR(255),  -- 回复的邮件 ID
    references TEXT,  -- 邮件链引用
    
    -- 元数据
    has_attachments BOOLEAN DEFAULT FALSE,
    is_read BOOLEAN DEFAULT FALSE,
    is_draft BOOLEAN DEFAULT FALSE,
    importance VARCHAR(20),  -- low, normal, high
    categories JSONB,  -- ["系统操作", "Bug反馈"]
    
    -- 处理状态
    processed_at TIMESTAMP WITH TIME ZONE,
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processed, failed
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_emails_conversation ON emails(conversation_id);
CREATE INDEX idx_emails_sender ON emails(sender_email);
CREATE INDEX idx_emails_sent_at ON emails(sent_at);
CREATE INDEX idx_emails_status ON emails(processing_status);

-- ============================================
-- 2. 邮件线程表
-- ============================================
CREATE TABLE email_threads (
    id VARCHAR(255) PRIMARY KEY,  -- conversation_id
    subject TEXT,
    
    -- 参与者
    initiator_email VARCHAR(255),  -- 发起人
    initiator_name VARCHAR(255),
    support_members JSONB,  -- ["nickxu@culines.com", "yp@culines.com"]
    
    -- 统计
    email_count INTEGER DEFAULT 0,
    first_email_at TIMESTAMP WITH TIME ZONE,
    last_email_at TIMESTAMP WITH TIME ZONE,
    
    -- 分类
    category VARCHAR(50),  -- 系统操作, Bug反馈, 数据查询, 权限申请
    priority VARCHAR(20),  -- low, normal, high, urgent
    status VARCHAR(20),  -- open, resolved, closed
    
    -- 关联
    related_system VARCHAR(50),  -- Allegro, OPST, BI
    related_module VARCHAR(100),  -- 订舱模块, 报表模块
    
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(255),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_threads_status ON email_threads(status);
CREATE INDEX idx_threads_category ON email_threads(category);

-- ============================================
-- 3. 问答对表
-- ============================================
CREATE TABLE qa_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(255) REFERENCES email_threads(id),
    
    -- 问题
    question_email_id VARCHAR(255) REFERENCES emails(id),
    question_text TEXT NOT NULL,
    question_summary TEXT,  -- AI 生成的摘要
    question_keywords JSONB,  -- ["订舱", "修改"]
    question_embedding VECTOR(1536),  -- OpenAI embedding 维度
    
    asked_by_email VARCHAR(255),
    asked_by_name VARCHAR(255),
    asked_at TIMESTAMP WITH TIME ZONE,
    
    -- 答案
    answer_email_id VARCHAR(255) REFERENCES emails(id),
    answer_text TEXT NOT NULL,
    answer_summary TEXT,  -- AI 生成的摘要
    answer_keywords JSONB,
    
    answered_by_email VARCHAR(255),
    answered_by_name VARCHAR(255),
    answered_at TIMESTAMP WITH TIME ZONE,
    
    -- 质量
    confidence_score DECIMAL(3, 2),  -- 0.00 - 1.00
    is_verified BOOLEAN DEFAULT FALSE,  -- 人工验证
    helpful_count INTEGER DEFAULT 0,
    
    -- 分类
    category VARCHAR(50),
    subcategory VARCHAR(100),
    tags JSONB,  -- ["高频问题", "新手友好", "常见错误"]
    
    -- 关联
    related_system VARCHAR(50),
    related_module VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_qa_category ON qa_pairs(category);
CREATE INDEX idx_qa_asked_by ON qa_pairs(asked_by_email);
CREATE INDEX idx_qa_answered_by ON qa_pairs(answered_by_email);
CREATE INDEX idx_qa_confidence ON qa_pairs(confidence_score);

-- 向量索引 (需要 pgvector 扩展)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE INDEX idx_qa_embedding ON qa_pairs USING ivfflat (question_embedding vector_cosine_ops);

-- ============================================
-- 4. 用户表（IT/KC 人员）
-- ============================================
CREATE TABLE support_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    department VARCHAR(100),
    role VARCHAR(50),  -- IT Support, KC, Manager
    
    -- 统计
    total_replies INTEGER DEFAULT 0,
    avg_response_time_minutes INTEGER,
    avg_helpful_score DECIMAL(3, 2),
    
    -- 专业领域
    expertise_tags JSONB,  -- ["Allegro订舱", "报表查询", "权限管理"]
    
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_members_email ON support_members(email);

-- ============================================
-- 5. 自动回复记录表
-- ============================================
CREATE TABLE auto_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    incoming_email_id VARCHAR(255) REFERENCES emails(id),
    qa_pair_id UUID REFERENCES qa_pairs(id),
    
    -- 内容
    question_text TEXT,
    generated_reply_text TEXT,
    
    -- 决策
    confidence_score DECIMAL(3, 2),
    decision VARCHAR(20),  -- auto_sent, manual_review, rejected
    decision_reason TEXT,
    
    -- 执行
    sent_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    review_status VARCHAR(20),  -- approved, modified, rejected
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auto_replies_decision ON auto_replies(decision);
CREATE INDEX idx_auto_replies_sent_at ON auto_replies(sent_at);

-- ============================================
-- 6. 用户反馈表
-- ============================================
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    qa_pair_id UUID REFERENCES qa_pairs(id),
    auto_reply_id UUID REFERENCES auto_replies(id),
    
    -- 反馈内容
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    is_helpful BOOLEAN,
    comment TEXT,
    
    -- 反馈人
    feedback_by_email VARCHAR(255),
    feedback_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_qa ON feedback(qa_pair_id);

-- ============================================
-- 7. 知识库更新日志
-- ============================================
CREATE TABLE knowledge_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    action VARCHAR(50),  -- insert, update, delete
    table_name VARCHAR(50),
    record_id VARCHAR(255),
    
    changes JSONB,  -- 变更内容
    
    updated_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_updates_table ON knowledge_updates(table_name);

-- ============================================
-- 视图：常见问题统计
-- ============================================
CREATE VIEW v_common_questions AS
SELECT 
    category,
    question_summary,
    COUNT(*) as occurrence_count,
    AVG(confidence_score) as avg_confidence,
    AVG(helpful_count) as avg_helpful,
    MAX(updated_at) as last_asked_at
FROM qa_pairs
WHERE is_verified = TRUE
GROUP BY category, question_summary
HAVING COUNT(*) >= 3
ORDER BY occurrence_count DESC;

-- ============================================
-- 视图：团队成员绩效
-- ============================================
CREATE VIEW v_member_performance AS
SELECT 
    sm.email,
    sm.name,
    sm.department,
    COUNT(qa.id) as total_answers,
    AVG(qa.confidence_score) as avg_confidence,
    AVG(qa.helpful_count) as avg_helpful,
    sm.expertise_tags
FROM support_members sm
LEFT JOIN qa_pairs qa ON qa.answered_by_email = sm.email
GROUP BY sm.id
ORDER BY total_answers DESC;

-- ============================================
-- 函数：更新时间戳
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要自动更新的表创建触发器
CREATE TRIGGER update_emails_updated_at BEFORE UPDATE ON emails
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_threads_updated_at BEFORE UPDATE ON email_threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_qa_updated_at BEFORE UPDATE ON qa_pairs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_members_updated_at BEFORE UPDATE ON support_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
