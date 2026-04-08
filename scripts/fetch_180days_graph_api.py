#!/usr/bin/env python3
"""
使用 Microsoft Graph API 采集 allegrosupport@culines.com 过去180天的邮件
适合服务器环境运行

使用前需配置环境变量（.env文件）：
- GRAPH_TENANT_ID: Azure AD 租户ID
- GRAPH_CLIENT_ID: 应用注册客户端ID  
- GRAPH_CLIENT_SECRET: 客户端密钥
- MAILBOX: allegrosupport@culines.com
"""

import os
import sys
import json
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
env_path = Path(__file__).parent.parent / 'config' / '.env'
load_dotenv(env_path)

# IT 同事白名单（回答者）
SUPPORT_SENDERS = {
    'kieranji@culines.com',
    'joanneding@culines.com',
    'catherinekang@culines.com'
}


class GraphAPIClient:
    """Microsoft Graph API 客户端"""
    
    def __init__(self):
        self.tenant_id = os.getenv('GRAPH_TENANT_ID')
        self.client_id = os.getenv('GRAPH_CLIENT_ID')
        self.client_secret = os.getenv('GRAPH_CLIENT_SECRET')
        self.mailbox = os.getenv('MAILBOX', 'allegrosupport@culines.com')
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("缺少 Graph API 配置，请检查 .env 文件")
        
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self) -> str:
        """获取访问令牌"""
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        self.token_expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'] - 300)
        
        logger.info("成功获取 Graph API 访问令牌")
        return self.access_token
    
    def get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }
    
    def get_messages(self, days: int = 180, top: int = 100, skip: int = 0) -> List[Dict]:
        """获取邮件列表"""
        start_date = datetime.now() - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 获取发给或来自 allegrosupport 的邮件
        filter_query = f"(toRecipients/any(r:r/emailAddress/address eq '{self.mailbox}') or from/emailAddress/address eq '{self.mailbox}') and receivedDateTime ge {start_date_str}"
        
        url = f"https://graph.microsoft.com/v1.0/users/{self.mailbox}/messages"
        params = {
            '$filter': filter_query,
            '$top': top,
            '$skip': skip,
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,conversationId,subject,from,toRecipients,receivedDateTime,body,hasAttachments'
        }
        
        response = requests.get(url, headers=self.get_headers(), params=params)
        response.raise_for_status()
        
        return response.json().get('value', [])
    
    def get_all_messages(self, days: int = 180) -> List[Dict]:
        """获取所有邮件（自动分页）"""
        all_messages = []
        skip = 0
        top = 100
        
        while True:
            messages = self.get_messages(days=days, top=top, skip=skip)
            if not messages:
                break
            
            all_messages.extend(messages)
            logger.info(f"已获取 {len(all_messages)} 封邮件...")
            
            if len(messages) < top:
                break
            skip += top
        
        return all_messages


def parse_message(message: Dict) -> Dict:
    """解析 Graph API 邮件格式"""
    sender_email = message.get('from', {}).get('emailAddress', {}).get('address', '').lower()
    sender_name = message.get('from', {}).get('emailAddress', {}).get('name', '')
    
    # 判断角色
    role = 'support' if sender_email in SUPPORT_SENDERS else 'external'
    
    return {
        'id': message.get('id'),
        'subject': message.get('subject'),
        'sender_name': sender_name,
        'sender_email': sender_email,
        'sender_role': role,
        'received_time': message.get('receivedDateTime'),
        'body': message.get('body', {}).get('content', ''),
        'conversation_id': message.get('conversationId'),
        'has_attachments': message.get('hasAttachments', False),
        'to_recipients': [r.get('emailAddress', {}).get('address', '') 
                         for r in message.get('toRecipients', [])]
    }


def group_by_conversation(emails: List[Dict]) -> Dict:
    """按会话分组"""
    conversations = defaultdict(list)
    for email in emails:
        topic = email.get('conversation_id') or email['subject']
        conversations[topic].append(email)
    
    # 按时间排序
    for topic in conversations:
        conversations[topic].sort(key=lambda x: x['received_time'])
    
    return dict(conversations)


def extract_qa_pairs(conversations: Dict) -> List[Dict]:
    """提取问答对"""
    qa_pairs = []
    qa_id = 0
    
    for topic, emails in conversations.items():
        if len(emails) < 2:
            continue
        
        questions = [e for e in emails if e['sender_role'] == 'external']
        answers = [e for e in emails if e['sender_role'] == 'support']
        
        for q in questions:
            reply = None
            for a in answers:
                if a['received_time'] > q['received_time']:
                    reply = a
                    break
            
            if reply:
                qa_id += 1
                qa_pairs.append({
                    'id': f'qa_{qa_id}',
                    'subject': topic,
                    'question': {
                        'text': q['body'],
                        'sender': q['sender_name'],
                        'sender_email': q['sender_email'],
                        'time': q['received_time']
                    },
                    'answer': {
                        'text': reply['body'],
                        'responder': reply['sender_name'],
                        'responder_email': reply['sender_email'],
                        'time': reply['received_time']
                    }
                })
    
    return qa_pairs


def categorize_qa(qa_pairs: List[Dict]) -> List[Dict]:
    """分类问答对"""
    categories = {
        '订舱操作': ['booking', '订舱', 'SO', 'slot', 'container', 'vd', 'vessel'],
        '提单操作': ['BL', 'bill of lading', '提单', 'manifest'],
        '报关操作': ['customs', '报关', 'declaration', 'clearance'],
        '费用相关': ['invoice', '费用', 'payment', 'charge'],
        '系统问题': ['error', 'bug', 'system', 'issue', 'failed'],
        '数据修改': ['update', 'modify', 'change', 'edit', '数据'],
        '权限申请': ['access', '权限', 'account', 'login', 'password'],
        '其他': []
    }
    
    for qa in qa_pairs:
        text = (qa['question']['text'] + ' ' + qa['answer']['text']).lower()
        assigned = False
        
        for cat, keywords in categories.items():
            if cat == '其他':
                continue
            for kw in keywords:
                if kw in text:
                    qa['category'] = cat
                    assigned = True
                    break
            if assigned:
                break
        
        if not assigned:
            qa['category'] = '其他'
    
    return qa_pairs


def save_to_binary_structure(emails: List[Dict], qa_pairs: List[Dict], output_dir: Path):
    """保存到二元分离结构"""
    print(f"\n保存到二元分离结构: {output_dir}")
    
    # 创建目录
    raw_emails_dir = output_dir / 'raw' / 'emails' / '2026'
    raw_threads_dir = output_dir / 'raw' / 'threads'
    wiki_qa_dir = output_dir / 'wiki' / 'qa'
    wiki_cat_dir = output_dir / 'wiki' / 'categories'
    
    for d in [raw_emails_dir, raw_threads_dir, wiki_qa_dir, wiki_cat_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 保存原始邮件
    print("  保存原始邮件...")
    for email in emails:
        received = datetime.fromisoformat(email['received_time'].replace('Z', '+00:00'))
        month_dir = raw_emails_dir / received.strftime('%m')
        month_dir.mkdir(exist_ok=True)
        
        with open(month_dir / f"{email['id']}.json", 'w', encoding='utf-8') as f:
            json.dump(email, f, ensure_ascii=False, indent=2)
    
    # 保存 wiki QA
    print("  保存问答对...")
    for qa in qa_pairs:
        # 提取关键词
        text = qa['question']['text'] + ' ' + qa['answer']['text']
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        word_freq = defaultdict(int)
        for w in words:
            word_freq[w] += 1
        top_keywords = sorted(word_freq.items(), key=lambda x: -x[1])[:10]
        
        wiki_qa = {
            'id': qa['id'],
            'classification': {
                'category': qa.get('category', '其他'),
                'confidence': 0.8,
                'tags': [w for w, _ in top_keywords]
            },
            'question': {
                'text': qa['question']['text'],
                'summary': qa['question']['text'][:200] + '...',
                'keywords': [w for w, _ in top_keywords[:5]],
                'sender': {'name': qa['question']['sender'], 'email': qa['question']['sender_email'], 'role': 'external'}
            },
            'answer': {
                'text': qa['answer']['text'],
                'summary': qa['answer']['text'][:200] + '...',
                'responder': {'name': qa['answer']['responder'], 'email': qa['answer']['responder_email'], 'role': 'support'}
            },
            'quality': {'confidence_score': 0.85, 'completeness': 'complete'},
            'history': [{'action': 'created', 'timestamp': datetime.now().isoformat(), 'note': 'Graph API 180天采集'}]
        }
        
        with open(wiki_qa_dir / f"{qa['id']}.json", 'w', encoding='utf-8') as f:
            json.dump(wiki_qa, f, ensure_ascii=False, indent=2)
    
    # 保存分类索引
    cat_count = defaultdict(list)
    for qa in qa_pairs:
        cat_count[qa.get('category', '其他')].append(qa['id'])
    
    for cat, qa_ids in cat_count.items():
        cat_path = wiki_cat_dir / cat
        cat_path.mkdir(exist_ok=True)
        with open(cat_path / 'index.json', 'w', encoding='utf-8') as f:
            json.dump({'category': cat, 'total': len(qa_ids), 'qa_ids': qa_ids}, f, ensure_ascii=False, indent=2)
    
    # 保存搜索索引
    search_records = []
    for qa in qa_pairs:
        search_records.append({
            'id': qa['id'],
            'category': qa.get('category', '其他'),
            'question_summary': qa['question']['text'][:100],
            'answer_summary': qa['answer']['text'][:100]
        })
    
    with open(output_dir / 'wiki' / 'search_index.json', 'w', encoding='utf-8') as f:
        json.dump({'version': '1.0', 'total': len(search_records), 'records': search_records}, f, ensure_ascii=False, indent=2)
    
    print(f"  完成: {len(emails)} 封邮件, {len(qa_pairs)} 个问答对")


def main():
    print("=" * 60)
    print("AllegroSupport 180天邮件采集 (Graph API)")
    print("=" * 60)
    
    try:
        # 初始化客户端
        client = GraphAPIClient()
        
        # 获取邮件
        print("\n开始采集邮件...")
        messages = client.get_all_messages(days=180)
        
        if not messages:
            print("未找到邮件，请检查:")
            print("  1. Graph API 权限是否配置正确")
            print("  2. 应用是否有 Mail.Read 权限")
            print("  3. 邮箱地址是否正确")
            return
        
        print(f"\n共获取 {len(messages)} 封邮件")
        
        # 解析邮件
        emails = [parse_message(m) for m in messages]
        
        # 分组和提取问答对
        conversations = group_by_conversation(emails)
        print(f"会话线程: {len(conversations)} 个")
        
        qa_pairs = extract_qa_pairs(conversations)
        print(f"问答对: {len(qa_pairs)} 个")
        
        # 分类
        qa_pairs = categorize_qa(qa_pairs)
        
        # 统计
        cat_stats = defaultdict(int)
        for qa in qa_pairs:
            cat_stats[qa.get('category', '其他')] += 1
        
        print("\n分类统计:")
        for cat, count in sorted(cat_stats.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count} 个")
        
        # 保存
        output_dir = Path(__file__).parent.parent / 'data_180days_graph'
        save_to_binary_structure(emails, qa_pairs, output_dir)
        
        # 保存标准格式
        standard = {
            'total': len(qa_pairs),
            'categories': dict(cat_stats),
            'qa_pairs': qa_pairs,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'days_covered': 180,
                'source': 'Graph API'
            }
        }
        with open(output_dir / 'qa_pairs_180days.json', 'w', encoding='utf-8') as f:
            json.dump(standard, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 完成！数据保存到: {output_dir}/")
        
    except ValueError as e:
        print(f"\n配置错误: {e}")
        print("\n请创建 allegrosupport-kb/config/.env 文件，内容如下:")
        print("  GRAPH_TENANT_ID=your-tenant-id")
        print("  GRAPH_CLIENT_ID=your-client-id")
        print("  GRAPH_CLIENT_SECRET=your-client-secret")
        print("  MAILBOX=allegrosupport@culines.com")
    except Exception as e:
        print(f"\n错误: {e}")
        raise


if __name__ == '__main__':
    main()
