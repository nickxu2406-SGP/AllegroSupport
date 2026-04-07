#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原型验证：邮件问答对提取演示
使用示例邮件演示完整的处理流程
"""

import sys
import io

# 设置 Windows 控制台输出编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple

# 模拟示例邮件数据（基于实际场景）
SAMPLE_EMAILS = [
    # 邮件 1：问题
    {
        "id": "email_001",
        "conversation_id": "conv_12345",
        "subject": "【咨询】如何在 Allegro 中修改已提交的订舱申请？",
        "sender_email": "zhang.san@customer.com",
        "sender_name": "张三",
        "recipients": ["allegrosupport@culines.com"],
        "cc": [],
        "received_at": "2026-04-01T09:30:00Z",
        "sent_at": "2026-04-01T09:30:00Z",
        "body_text": """
您好，

我是 ABC 货代的张三。

请问如何在 Allegro 系统中修改已经提交的订舱申请？

我昨天提交了一个 NSCT1 航线的订舱申请，集装箱数量填错了，需要从 5 个改为 3 个。
订单号是：BK2026033100123

请指导一下操作步骤，谢谢！

此致
张三
ABC 货代
电话：138-xxxx-xxxx
        """.strip(),
        "in_reply_to": None,
    },
    
    # 邮件 2：第一次回复（IT 支持人员）
    {
        "id": "email_002",
        "conversation_id": "conv_12345",
        "subject": "RE: 【咨询】如何在 Allegro 中修改已提交的订舱申请？",
        "sender_email": "nickxu@culines.com",
        "sender_name": "Nick Xu",
        "recipients": ["zhang.san@customer.com"],
        "cc": ["allegrosupport@culines.com"],
        "received_at": "2026-04-01T10:15:00Z",
        "sent_at": "2026-04-01T10:15:00Z",
        "body_text": """
张三，您好！

关于修改已提交的订舱申请，有两种情况：

**情况 1：订单尚未审核**
如果订单状态是"待审核"，可以直接在系统中修改：
1. 登录 Allegro 系统
2. 进入【订舱管理】→【我的订舱】
3. 找到订单 BK2026033100123，点击【编辑】按钮
4. 修改集装箱数量后，点击【保存并重新提交】

**情况 2：订单已审核**
如果订单状态是"已审核"或"已确认"，需要申请撤回：
1. 在订单详情页点击【申请撤回】
2. 填写撤回原因
3. 等待审核通过后（通常 1-2 小时）
4. 重新编辑并提交

请先查看订单状态，如果不确定可以告诉我订单号，我帮您查看。

Best regards,
Nick Xu
IT Support Team
        """.strip(),
        "in_reply_to": "email_001",
    },
    
    # 邮件 3：用户补充信息
    {
        "id": "email_003",
        "conversation_id": "conv_12345",
        "subject": "RE: 【咨询】如何在 Allegro 中修改已提交的订舱申请？",
        "sender_email": "zhang.san@customer.com",
        "sender_name": "张三",
        "recipients": ["nickxu@culines.com"],
        "cc": ["allegrosupport@culines.com"],
        "received_at": "2026-04-01T10:30:00Z",
        "sent_at": "2026-04-01T10:30:00Z",
        "body_text": """
Nick，您好！

订单状态显示"已审核"，那我需要申请撤回。

请问撤回审核需要多久？比较急，因为截关时间快到了。

另外，如果撤回后重新提交，会影响舱位吗？

谢谢！
张三
        """.strip(),
        "in_reply_to": "email_002",
    },
    
    # 邮件 4：最终解决方案
    {
        "id": "email_004",
        "conversation_id": "conv_12345",
        "subject": "RE: 【咨询】如何在 Allegro 中修改已提交的订舱申请？",
        "sender_email": "nickxu@culines.com",
        "sender_name": "Nick Xu",
        "recipients": ["zhang.san@customer.com"],
        "cc": ["allegrosupport@culines.com"],
        "received_at": "2026-04-01T10:45:00Z",
        "sent_at": "2026-04-01T10:45:00Z",
        "body_text": """
张三，您好！

**撤回时间**：
- 正常情况 1-2 小时
- 如果是加急情况，可以联系客服加急处理（电话：400-xxx-xxxx）
- 我已经帮您标记为加急，预计 30 分钟内完成

**关于舱位**：
- 撤回重新提交不会影响舱位
- NSCT1 航线舱位充足，可以放心修改
- 建议尽快重新提交，避免临近截关

**操作步骤总结**：
1. 在订单详情页点击【申请撤回】（我已经帮您加速处理）
2. 等待撤回完成（预计 30 分钟）
3. 收到撤回通知后，进入【我的订舱】编辑订单
4. 修改集装箱数量为 3，重新提交

如有其他问题，随时联系！

Best regards,
Nick Xu
IT Support Team
        """.strip(),
        "in_reply_to": "email_003",
    },
    
    # 邮件 5：另一个问题
    {
        "id": "email_005",
        "conversation_id": "conv_67890",
        "subject": "【求助】Allegro 报表导出失败，提示权限不足",
        "sender_email": "li.si@customer.com",
        "sender_name": "李四",
        "recipients": ["allegrosupport@culines.com"],
        "cc": [],
        "received_at": "2026-04-02T14:20:00Z",
        "sent_at": "2026-04-02T14:20:00Z",
        "body_text": """
您好，

我在导出订舱统计报表时，系统提示"权限不足，请联系管理员"。

用户账号：lisi@abc-forwarder.com
需要的报表：【订舱管理】→【统计报表】→【月度汇总】

请帮忙开通权限，谢谢！

李四
ABC 货代
        """.strip(),
        "in_reply_to": None,
    },
    
    # 邮件 6：回复
    {
        "id": "email_006",
        "conversation_id": "conv_67890",
        "subject": "RE: 【求助】Allegro 报表导出失败，提示权限不足",
        "sender_email": "ypteo@culines.com",
        "sender_name": "YP Teo",
        "recipients": ["li.si@customer.com"],
        "cc": ["allegrosupport@culines.com"],
        "received_at": "2026-04-02T15:00:00Z",
        "sent_at": "2026-04-02T15:00:00Z",
        "body_text": """
李四，您好！

已为您开通报表导出权限。

**权限范围**：
- ✅ 月度汇总报表
- ✅ 订舱明细报表
- ✅ 运费统计报表

**生效时间**：立即生效

**使用方法**：
1. 登录 Allegro 系统
2. 进入【订舱管理】→【统计报表】
3. 选择【月度汇总】，设置时间范围
4. 点击【导出 Excel】或【导出 PDF】

如果还有其他权限需求，请联系您的商务经理或发邮件到此邮箱。

Best regards,
YP Teo
IT Support Team
        """.strip(),
        "in_reply_to": "email_005",
    },
]


class EmailThreadBuilder:
    """邮件线程构建器"""
    
    def build_threads(self, emails: List[Dict]) -> Dict[str, List[Dict]]:
        """按 conversation_id 分组构建线程"""
        threads = {}
        
        for email in emails:
            conv_id = email['conversation_id']
            if conv_id not in threads:
                threads[conv_id] = []
            threads[conv_id].append(email)
        
        # 按时间排序
        for conv_id in threads:
            threads[conv_id].sort(key=lambda x: x['sent_at'])
        
        return threads


class QAExtractor:
    """问答对提取器"""
    
    SUPPORT_DOMAINS = [
        "culines.com",
        # 可以添加更多内部域名
    ]
    
    def is_internal_email(self, email: str) -> bool:
        """判断是否为内部支持人员邮箱"""
        if not email:
            return False
        return any(domain in email.lower() for domain in self.SUPPORT_DOMAINS)
    
    def clean_email_body(self, body: str) -> str:
        """清洗邮件正文"""
        # 移除签名
        patterns = [
            r'Best regards,.*$',
            r'此致.*$',
            r'--\s*\n.*$',
            r'电话：.*$',
        ]
        
        cleaned = body
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)
        
        # 移除多余空行
        cleaned = '\n'.join(line for line in cleaned.split('\n') if line.strip())
        
        return cleaned.strip()
    
    def extract_qa_pairs(self, thread: List[Dict]) -> List[Dict]:
        """
        从邮件线程中提取问答对
        
        逻辑：
        1. 外部用户提问 → IT 回复 = 问答对
        2. 如果有多次交互，提取最后的完整解决方案
        """
        qa_pairs = []
        
        # 找到所有外部邮件（问题）
        external_emails = [
            email for email in thread 
            if not self.is_internal_email(email['sender_email'])
        ]
        
        # 找到所有内部邮件（回复）
        internal_emails = [
            email for email in thread 
            if self.is_internal_email(email['sender_email'])
        ]
        
        if not external_emails or not internal_emails:
            return qa_pairs
        
        # 提取问答对
        # 简化逻辑：取第一个外部邮件作为问题，最后一个内部邮件作为答案
        question_email = external_emails[0]
        answer_email = internal_emails[-1]  # 取最后的回复（通常最完整）
        
        # 清洗文本
        question_text = self.clean_email_body(question_email['body_text'])
        answer_text = self.clean_email_body(answer_email['body_text'])
        
        # 提取关键词（简单实现，实际可用 NLP）
        keywords = self.extract_keywords(question_text)
        
        # 分类
        category = self.classify_question(question_text)
        
        qa_pair = {
            'thread_id': thread[0]['conversation_id'],
            'question': {
                'text': question_text,
                'summary': question_email['subject'],
                'keywords': keywords,
                'asked_by': question_email['sender_name'],
                'asked_at': question_email['sent_at'],
            },
            'answer': {
                'text': answer_text,
                'responded_by': answer_email['sender_name'],
                'responded_at': answer_email['sent_at'],
            },
            'metadata': {
                'category': category,
                'system': 'Allegro',
                'module': self.detect_module(question_text),
            }
        }
        
        qa_pairs.append(qa_pair)
        
        return qa_pairs
    
    def extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单实现）"""
        keywords = []
        
        # 系统名称
        if 'allegro' in text.lower():
            keywords.append('Allegro')
        
        # 操作关键词
        operation_keywords = ['修改', '删除', '导出', '查询', '提交', '撤回', '权限']
        for kw in operation_keywords:
            if kw in text:
                keywords.append(kw)
        
        return keywords
    
    def classify_question(self, text: str) -> str:
        """问题分类"""
        text_lower = text.lower()
        
        if any(word in text for word in ['权限', '开通', '无法访问']):
            return '权限申请'
        elif any(word in text for word in ['修改', '删除', '编辑']):
            return '系统操作'
        elif any(word in text for word in ['报错', '失败', '错误', 'bug']):
            return 'Bug反馈'
        elif any(word in text for word in ['查询', '导出', '报表']):
            return '数据查询'
        else:
            return '其他'
    
    def detect_module(self, text: str) -> str:
        """检测相关模块"""
        if any(word in text for word in ['订舱', 'booking']):
            return '订舱模块'
        elif any(word in text for word in ['报表', '统计']):
            return '报表模块'
        elif any(word in text for word in ['权限']):
            return '权限管理'
        else:
            return '其他'


def demo_qa_extraction():
    """演示：问答对提取"""
    print("=" * 80)
    print("[邮件] 问答对提取演示")
    print("=" * 80)
    print()
    
    # 1. 构建邮件线程
    print("【步骤 1】构建邮件线程...")
    builder = EmailThreadBuilder()
    threads = builder.build_threads(SAMPLE_EMAILS)
    print(f"[OK] 识别到 {len(threads)} 个邮件线程\n")
    
    # 2. 提取问答对
    print("【步骤 2】提取问答对...")
    extractor = QAExtractor()
    
    all_qa_pairs = []
    for conv_id, thread in threads.items():
        print(f"\n--- 线程: {conv_id} ({len(thread)} 封邮件) ---")
        
        qa_pairs = extractor.extract_qa_pairs(thread)
        all_qa_pairs.extend(qa_pairs)
        
        for qa in qa_pairs:
            print(f"\n[*] 问题分类: {qa['metadata']['category']}")
            print(f"   关键词: {', '.join(qa['question']['keywords'])}")
            print(f"   提问人: {qa['question']['asked_by']}")
            print(f"   问题摘要: {qa['question']['summary']}")
            print(f"   问题内容: {qa['question']['text'][:100]}...")
            print(f"\n   回复人: {qa['answer']['responded_by']}")
            print(f"   答案内容: {qa['answer']['text'][:150]}...")
    
    print(f"\n[OK] 提取到 {len(all_qa_pairs)} 个问答对\n")
    
    # 3. 保存结果
    output_file = '../data/qa_pairs_demo.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_qa_pairs, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] 问答对已保存到: {output_file}")
    
    return all_qa_pairs


def demo_semantic_search(qa_pairs: List[Dict]):
    """演示：语义检索（模拟）"""
    print("\n" + "=" * 80)
    print("[搜索] 语义检索演示（模拟）")
    print("=" * 80)
    print()
    
    # 模拟新问题
    new_questions = [
        "我想修改已经提交的订舱申请，怎么操作？",
        "导出报表时提示权限不足怎么办？",
    ]
    
    print("【模拟场景】收到新邮件，自动匹配历史答案\n")
    
    for i, question in enumerate(new_questions, 1):
        print(f"\n--- 新问题 {i} ---")
        print(f"问题: {question}")
        print("\n【检索中...】")
        
        # 简单关键词匹配（实际应用用向量相似度）
        best_match = None
        best_score = 0
        
        for qa in qa_pairs:
            score = 0
            question_lower = question.lower()
            qa_text = qa['question']['text'].lower() + ' ' + qa['question']['summary'].lower()
            
            # 关键词匹配
            for keyword in qa['question']['keywords']:
                if keyword.lower() in question_lower:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = qa
        
        if best_match:
            print(f"[OK] 找到匹配的历史问答（置信度: {best_score/len(best_match['question']['keywords']):.0%}）")
            print(f"\n【历史问题】{best_match['question']['summary']}")
            print(f"【历史答案】{best_match['answer']['text'][:200]}...")
            print(f"\n【回复建议】")
            print(f"---")
            print(f"您好，")
            print(f"")
            print(f"关于您的问题，参考以下解决方案：")
            print(f"")
            print(f"{best_match['answer']['text']}")
            print(f"")
            print(f"如有其他问题，随时联系！")
            print(f"---")
        else:
            print("[X] 未找到匹配的历史问答，需要人工回复")


def main():
    """主演示流程"""
    print("\n" + "[*] AllegroSupport 邮件知识库原型验证")
    print()
    
    # 步骤 1: 问答对提取
    qa_pairs = demo_qa_extraction()
    
    # 步骤 2: 语义检索
    demo_semantic_search(qa_pairs)
    
    print("\n" + "=" * 80)
    print("[OK] 原型验证完成！")
    print("=" * 80)
    print("\n【总结】")
    print("1. [OK] 邮件线程识别：成功识别 2 个线程")
    print("2. [OK] 问答对提取：提取 2 个有效问答对")
    print("3. [OK] 问题分类：自动分类为'系统操作'和'权限申请'")
    print("4. [OK] 关键词提取：自动提取关键标签")
    print("5. [OK] 语义检索：成功匹配历史答案并生成回复建议")
    print("\n【下一步】")
    print("- 集成真实 Graph API 数据")
    print("- 接入向量数据库（ChromaDB）实现真正的语义检索")
    print("- 使用大模型（DeepSeek）优化答案生成")


if __name__ == '__main__':
    main()
