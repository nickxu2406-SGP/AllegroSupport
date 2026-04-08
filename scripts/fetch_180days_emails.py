#!/usr/bin/env python3
"""
采集 allegrosupport@culines.com 过去180天的邮件
使用 Outlook COM 接口（无需 Graph API 配置）
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import win32com.client
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# IT 同事白名单（回答者）
SUPPORT_SENDERS = {
    'kieranji@culines.com',
    'joanneding@culines.com', 
    'catherinekang@culines.com'
}

def get_sender_role(sender_email):
    """判断发件人角色"""
    if not sender_email:
        return 'external'
    return 'support' if sender_email.lower() in SUPPORT_SENDERS else 'external'

def extract_email_from_sender(sender_string):
    """从发件人字符串中提取邮箱"""
    if not sender_string:
        return ''
    # 匹配 <email@domain.com> 格式
    match = re.search(r'<([^>]+@[^>]+)>', sender_string)
    if match:
        return match.group(1).lower()
    # 直接是邮箱格式
    if '@' in sender_string and '.' in sender_string:
        return sender_string.lower().strip()
    return sender_string.lower().strip()

def extract_name_from_sender(sender_string):
    """从发件人字符串中提取姓名"""
    if not sender_string:
        return ''
    # 去掉邮箱部分
    name = re.sub(r'<[^>]+>', '', sender_string).strip()
    return name

def parse_email_body(body):
    """解析邮件正文，提取关键信息"""
    if not body:
        return ''
    # 移除过多的换行
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()

def fetch_emails(days=180):
    """从 Outlook 采集邮件 - 搜索所有账户"""
    print(f"正在连接 Outlook，准备采集过去 {days} 天的邮件...")
    
    outlook = win32com.client.Dispatch('Outlook.Application')
    ns = outlook.GetNamespace('MAPI')
    
    emails = []
    email_ids = set()  # 去重
    
    # 计算起始日期
    start_date = datetime.now() - timedelta(days=days)
    
    # 遍历所有存储（账户）
    for store in ns.Stores:
        try:
            inbox = store.GetDefaultFolder(6)  # 收件箱
            print(f"\n  检查账户: {store.DisplayName} ({inbox.Items.Count} 封邮件)")
            
            # 获取所有项目
            items = inbox.Items
            items.Sort('[ReceivedTime]', True)  # 按时间倒序
            
            account_count = 0
            for item in items:
                try:
                    received = item.ReceivedTime
                    received_naive = received.replace(tzinfo=None)
                    
                    # 如果邮件早于起始日期，停止（因为是倒序）
                    if received_naive < start_date:
                        break
                    
                    # 获取收件人列表
                    recipients = []
                    try:
                        for r in item.Recipients:
                            addr = r.Address.lower() if r.Address else ''
                            recipients.append(addr)
                    except:
                        pass
                    
                    # 获取发件人
                    sender = str(item.SenderEmailAddress) if item.SenderEmailAddress else ''
                    sender_lower = sender.lower()
                    
                    # 检查是否是 allegrosupport 相关邮件
                    is_to_allegrosupport = any('allegrosupport' in r for r in recipients)
                    is_from_allegrosupport = 'allegrosupport' in sender_lower
                    is_from_support_team = any(s in sender_lower for s in SUPPORT_SENDERS)
                    
                    # 采集条件：发给allegrosupport 或 来自IT支持团队
                    if not (is_to_allegrosupport or is_from_allegrosupport or is_from_support_team):
                        continue
                    
                    # 去重（使用 EntryID）
                    entry_id = getattr(item, 'EntryID', None)
                    if entry_id and entry_id in email_ids:
                        continue
                    if entry_id:
                        email_ids.add(entry_id)
                    
                    sender_email = extract_email_from_sender(item.SenderEmailAddress)
                    sender_name = extract_name_from_sender(str(item.Sender))
                    
                    email_data = {
                        'id': f"email_{received_naive.strftime('%Y%m%d_%H%M%S')}_{len(emails)}",
                        'entry_id': entry_id,
                        'subject': item.Subject,
                        'sender_name': sender_name,
                        'sender_email': sender_email,
                        'sender_role': get_sender_role(sender_email),
                        'received_time': received_naive.isoformat(),
                        'sent_time': item.SentTime.replace(tzinfo=None).isoformat() if item.SentTime else None,
                        'body': parse_email_body(item.Body),
                        'body_preview': (item.Body[:500] + '...') if item.Body and len(item.Body) > 500 else item.Body,
                        'to_recipients': recipients,
                        'has_attachments': item.Attachments.Count > 0,
                        'conversation_id': getattr(item, 'ConversationID', None),
                        'conversation_topic': getattr(item, 'ConversationTopic', item.Subject),
                        'is_read': item.UnRead == False,
                        'source_account': store.DisplayName
                    }
                    
                    emails.append(email_data)
                    account_count += 1
                    
                    if account_count % 10 == 0:
                        print(f"    已采集 {account_count} 封...")
                        
                except Exception as e:
                    continue
            
            if account_count > 0:
                print(f"    账户 {store.DisplayName}: {account_count} 封")
                    
        except Exception as e:
            print(f"  跳过账户 {store.DisplayName}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"总共采集到 {len(emails)} 封相关邮件")
    print(f"  - 来自 {len(set(e['source_account'] for e in emails))} 个账户")
    print(f"  - 时间范围: {days} 天")
    return emails

def group_by_conversation(emails):
    """按会话（线程）分组邮件"""
    conversations = defaultdict(list)
    
    for email in emails:
        # 使用 ConversationTopic 作为会话标识
        topic = email.get('conversation_topic') or email['subject']
        # 简化主题（移除 Re: Fwd: 等前缀）
        clean_topic = re.sub(r'^(Re:|Fwd:|回复:|转发:)\s*', '', topic, flags=re.IGNORECASE)
        conversations[clean_topic].append(email)
    
    # 对每个会话内的邮件按时间排序
    for topic in conversations:
        conversations[topic].sort(key=lambda x: x['received_time'])
    
    return dict(conversations)

def extract_qa_pairs(conversations):
    """从会话中提取问答对"""
    qa_pairs = []
    qa_id = 0
    
    for topic, emails in conversations.items():
        if len(emails) < 2:
            continue  # 需要至少2封邮件才能形成问答
        
        # 找出第一封用户问题（external）和对应的 IT 回复（support）
        questions = [e for e in emails if e['sender_role'] == 'external']
        answers = [e for e in emails if e['sender_role'] == 'support']
        
        if not questions or not answers:
            continue
        
        # 为每个问题找最近的回复
        for q in questions:
            # 找这封问题之后的第一封 IT 回复
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
                    },
                    'metadata': {
                        'has_attachment': q['has_attachments'] or reply['has_attachments'],
                        'conversation_id': q.get('conversation_id'),
                        'thread_length': len(emails)
                    }
                })
    
    return qa_pairs

def categorize_qa(qa_pairs):
    """对问答对进行分类"""
    categories = {
        '订舱操作': ['booking', '订舱', 'SO', 'slot', 'container', 'vd', 'vessel', 'departure'],
        '提单操作': ['BL', 'bill of lading', '提单', 'manifest', 'shipper', 'consignee'],
        '报关操作': ['customs', '报关', 'declaration', 'clearance', 'cargo control'],
        '费用相关': ['invoice', '费用', 'payment', 'debit', 'credit', 'charge', 'freight'],
        '系统问题': ['error', 'bug', 'system', 'issue', 'problem', 'failed', 'cannot'],
        '数据修改': ['update', 'modify', 'change', 'edit', '数据', '修改', 'update route'],
        '权限申请': ['access', '权限', 'account', 'login', 'password', 'user', 'role'],
        '其他': []
    }
    
    for qa in qa_pairs:
        text = (qa['question']['text'] + ' ' + qa['answer']['text']).lower()
        assigned = False
        
        for category, keywords in categories.items():
            if category == '其他':
                continue
            for keyword in keywords:
                if keyword.lower() in text:
                    qa['category'] = category
                    assigned = True
                    break
            if assigned:
                break
        
        if not assigned:
            qa['category'] = '其他'
    
    return qa_pairs

def save_to_raw_wiki(emails, qa_pairs, output_dir):
    """保存到 raw/ 和 wiki/ 二元分离结构"""
    output_path = Path(output_dir)
    
    # 创建目录
    raw_dir = output_path / 'raw' / 'emails' / '2026'
    threads_dir = output_path / 'raw' / 'threads'
    wiki_qa_dir = output_path / 'wiki' / 'qa'
    wiki_cat_dir = output_path / 'wiki' / 'categories'
    
    for d in [raw_dir, threads_dir, wiki_qa_dir, wiki_cat_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    # 按年月组织原始邮件
    print("\n保存原始邮件到 raw/emails/...")
    email_index = {}
    for email in emails:
        received = datetime.fromisoformat(email['received_time'])
        year_month = received.strftime('%Y/%m')
        month_dir = raw_dir / received.strftime('%m')
        month_dir.mkdir(exist_ok=True)
        
        email_file = month_dir / f"{email['id']}.json"
        with open(email_file, 'w', encoding='utf-8') as f:
            json.dump(email, f, ensure_ascii=False, indent=2)
        
        email_index[email['id']] = {
            'path': f"emails/2026/{received.strftime('%m')}/{email['id']}.json",
            'received': email['received_time']
        }
    
    # 保存原始邮件索引
    with open(output_path / 'raw' / 'index.json', 'w', encoding='utf-8') as f:
        json.dump({
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'total_emails': len(emails),
            'emails_by_month': {}
        }, f, ensure_ascii=False, indent=2)
    
    # 保存问答对到 wiki/qa/
    print("保存问答对到 wiki/qa/...")
    for qa in qa_pairs:
        qa_file = wiki_qa_dir / f"{qa['id']}.json"
        
        # 提取关键词（简单的TF词频）
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
                'summary': qa['question']['text'][:200] + '...' if len(qa['question']['text']) > 200 else qa['question']['text'],
                'keywords': [w for w, _ in top_keywords[:5]],
                'sender': {
                    'name': qa['question']['sender'],
                    'email': qa['question']['sender_email'],
                    'role': 'external'
                },
                'original_email_id': f"email_{qa['question']['time']}"
            },
            'answer': {
                'text': qa['answer']['text'],
                'summary': qa['answer']['text'][:200] + '...' if len(qa['answer']['text']) > 200 else qa['answer']['text'],
                'responder': {
                    'name': qa['answer']['responder'],
                    'email': qa['answer']['responder_email'],
                    'role': 'support'
                }
            },
            'thread': {
                'id': f"thread_{qa['id']}",
                'path': f"../raw/threads/thread_{qa['id']}.json",
                'note': '原始线程记录'
            },
            'quality': {
                'confidence_score': 0.85,
                'completeness': 'complete' if len(qa['answer']['text']) > 100 else 'partial'
            },
            'history': [{
                'action': 'created',
                'timestamp': datetime.now().isoformat(),
                'note': '从180天邮件采集自动提取'
            }]
        }
        
        with open(qa_file, 'w', encoding='utf-8') as f:
            json.dump(wiki_qa, f, ensure_ascii=False, indent=2)
    
    # 创建分类索引
    print("创建分类索引...")
    cat_count = defaultdict(list)
    for qa in qa_pairs:
        cat = qa.get('category', '其他')
        cat_count[cat].append(qa['id'])
    
    for cat, qa_ids in cat_count.items():
        cat_dir = wiki_cat_dir / cat
        cat_dir.mkdir(exist_ok=True)
        
        with open(cat_dir / 'index.json', 'w', encoding='utf-8') as f:
            json.dump({
                'category': cat,
                'total': len(qa_ids),
                'qa_ids': qa_ids
            }, f, ensure_ascii=False, indent=2)
    
    # 创建搜索索引
    print("创建搜索索引...")
    search_records = []
    for qa in qa_pairs:
        wiki_qa_file = wiki_qa_dir / f"{qa['id']}.json"
        with open(wiki_qa_file, 'r', encoding='utf-8') as f:
            wiki_data = json.load(f)
        
        search_records.append({
            'id': qa['id'],
            'category': qa.get('category', '其他'),
            'question_keywords': wiki_data['question']['keywords'],
            'question_summary': wiki_data['question']['summary'][:100],
            'answer_summary': wiki_data['answer']['summary'][:100],
            'path': f"qa/{qa['id']}.json"
        })
    
    with open(output_path / 'wiki' / 'search_index.json', 'w', encoding='utf-8') as f:
        json.dump({
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'total': len(search_records),
            'records': search_records
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n保存完成:")
    print(f"  - 原始邮件: {len(emails)} 封 -> raw/emails/")
    print(f"  - 问答对: {len(qa_pairs)} 个 -> wiki/qa/")
    print(f"  - 分类: {len(cat_count)} 个 -> wiki/categories/")

def main():
    print("=" * 60)
    print("AllegroSupport 180天邮件采集与知识库归档")
    print("=" * 60)
    
    # 1. 采集邮件
    emails = fetch_emails(days=180)
    
    if not emails:
        print("未找到相关邮件，请检查:")
        print("  1. Outlook 是否已登录")
        print("  2. 是否有权限访问 allegrosupport@culines.com 邮箱")
        return
    
    # 2. 按会话分组
    print("\n按会话分组...")
    conversations = group_by_conversation(emails)
    print(f"共 {len(conversations)} 个会话线程")
    
    # 3. 提取问答对
    print("\n提取问答对...")
    qa_pairs = extract_qa_pairs(conversations)
    print(f"提取到 {len(qa_pairs)} 个问答对")
    
    # 4. 分类
    print("\n对问答对进行分类...")
    qa_pairs = categorize_qa(qa_pairs)
    
    # 统计分类
    cat_stats = defaultdict(int)
    for qa in qa_pairs:
        cat_stats[qa.get('category', '其他')] += 1
    
    print("\n分类统计:")
    for cat, count in sorted(cat_stats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 个")
    
    # 5. 保存到二元分离结构
    output_dir = Path(__file__).parent.parent / 'data_180days'
    print(f"\n保存到: {output_dir}")
    save_to_raw_wiki(emails, qa_pairs, output_dir)
    
    # 6. 同时更新现有的 qa_pairs.json 格式
    print("\n更新标准格式文件...")
    standard_output = {
        'total': len(qa_pairs),
        'categories': dict(cat_stats),
        'qa_pairs': qa_pairs,
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'days_covered': 180,
            'total_emails': len(emails),
            'total_conversations': len(conversations)
        }
    }
    
    with open(output_dir / 'qa_pairs_180days.json', 'w', encoding='utf-8') as f:
        json.dump(standard_output, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！文件保存位置: {output_dir}/")
    print("  - qa_pairs_180days.json (标准格式)")
    print("  - raw/ (原始邮件)")
    print("  - wiki/ (结构化知识库)")

if __name__ == '__main__':
    main()
