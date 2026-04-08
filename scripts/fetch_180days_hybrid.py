#!/usr/bin/env python3
"""
混合采集方案：
1. 加载现有的 _allegro_emails.json（90天基础数据）
2. 从 Outlook 个人收件箱采集增量 Allegro 邮件
3. 合并去重后生成180天知识库
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

# IT 同事白名单
SUPPORT_SENDERS = {
    'kieranji@culines.com',
    'joanneding@culines.com',
    'catherinekang@culines.com'
}

def get_sender_role(sender_email):
    if not sender_email:
        return 'external'
    return 'support' if sender_email.lower() in SUPPORT_SENDERS else 'external'

def parse_email_body(body):
    if not body:
        return ''
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()

def load_existing_data(filepath):
    """加载现有的 _allegro_emails.json"""
    print(f"加载现有数据: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 转换为统一格式
    emails = []
    
    # IT 回复
    for reply in data.get('it_replies', []):
        emails.append({
            'id': f"it_{reply.get('id', len(emails))}",
            'subject': reply.get('subject', ''),
            'sender_name': reply.get('responder', ''),
            'sender_email': reply.get('responder_email', ''),
            'sender_role': 'support',
            'received_time': reply.get('time', ''),
            'body': reply.get('text', ''),
            'source': 'existing_it_reply'
        })
    
    # 用户问题
    for q in data.get('user_questions', []):
        emails.append({
            'id': f"q_{q.get('id', len(emails))}",
            'subject': q.get('subject', ''),
            'sender_name': q.get('sender', ''),
            'sender_email': q.get('sender_email', ''),
            'sender_role': 'external',
            'received_time': q.get('time', ''),
            'body': q.get('text', ''),
            'source': 'existing_question'
        })
    
    print(f"  现有数据: {len(emails)} 封邮件")
    print(f"    - IT回复: {len(data.get('it_replies', []))}")
    print(f"    - 用户问题: {len(data.get('user_questions', []))}")
    return emails

def fetch_from_outlook(days=180):
    """从 Outlook 采集增量邮件"""
    print(f"\n从 Outlook 采集最近 {days} 天邮件...")
    
    outlook = win32com.client.Dispatch('Outlook.Application')
    ns = outlook.GetNamespace('MAPI')
    
    emails = []
    start_date = datetime.now() - timedelta(days=days)
    
    # 关键词匹配 Allegro 相关邮件
    allegro_keywords = ['allegro', 'booking', '订舱', 'SO', '提单', 'BL', 'container']
    
    for store in ns.Stores:
        try:
            inbox = store.GetDefaultFolder(6)
            items = inbox.Items
            items.Sort('[ReceivedTime]', True)
            
            account_count = 0
            for item in items:
                try:
                    received = item.ReceivedTime.replace(tzinfo=None)
                    if received < start_date:
                        break
                    
                    subject = item.Subject or ''
                    
                    # 检查是否 Allegro 相关
                    is_allegro_related = any(kw in subject.lower() for kw in allegro_keywords)
                    if not is_allegro_related:
                        continue
                    
                    # 获取发件人
                    sender_email = ''
                    try:
                        sender_email = item.SenderEmailAddress.lower()
                    except:
                        pass
                    
                    # 只采集来自/发给 IT 支持团队的邮件
                    is_from_support = sender_email in SUPPORT_SENDERS
                    
                    if not is_from_support:
                        continue
                    
                    emails.append({
                        'id': f"outlook_{received.strftime('%Y%m%d_%H%M%S')}_{len(emails)}",
                        'subject': subject,
                        'sender_name': str(item.Sender),
                        'sender_email': sender_email,
                        'sender_role': 'support',
                        'received_time': received.isoformat(),
                        'body': parse_email_body(item.Body),
                        'source': 'outlook_incremental',
                        'source_account': store.DisplayName
                    })
                    account_count += 1
                    
                except Exception as e:
                    continue
            
            if account_count > 0:
                print(f"  {store.DisplayName}: {account_count} 封")
                
        except Exception as e:
            continue
    
    print(f"  Outlook增量: {len(emails)} 封")
    return emails

def merge_emails(existing, incremental):
    """合并邮件，去重"""
    print("\n合并邮件数据...")
    
    # 使用主题+发件人+时间作为去重键
    seen = set()
    merged = []
    
    for email in existing + incremental:
        key = f"{email['subject']}|{email['sender_email']}|{email['received_time'][:10]}"
        if key not in seen:
            seen.add(key)
            merged.append(email)
    
    print(f"  合并后: {len(merged)} 封（去重 {len(existing) + len(incremental) - len(merged)} 封）")
    return merged

def group_by_conversation(emails):
    """按会话分组"""
    conversations = defaultdict(list)
    for email in emails:
        # 使用主题（去掉 Re: Fwd:）作为会话键
        subject = email['subject']
        clean_subject = re.sub(r'^(Re:|Fwd:|回复:|转发:)\s*', '', subject, flags=re.IGNORECASE)
        conversations[clean_subject].append(email)
    
    # 按时间排序
    for topic in conversations:
        conversations[topic].sort(key=lambda x: x['received_time'])
    
    return dict(conversations)

def extract_qa_pairs(conversations):
    """提取问答对"""
    print("\n提取问答对...")
    qa_pairs = []
    qa_id = 0
    
    for topic, emails in conversations.items():
        if len(emails) < 2:
            continue
        
        questions = [e for e in emails if e['sender_role'] == 'external']
        answers = [e for e in emails if e['sender_role'] == 'support']
        
        for q in questions:
            # 找最近的回复
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
    
    print(f"  提取到 {len(qa_pairs)} 个问答对")
    return qa_pairs

def categorize_qa(qa_pairs):
    """分类"""
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

def save_to_binary_structure(emails, qa_pairs, output_dir):
    """保存到二元分离结构"""
    print(f"\n保存到: {output_dir}")
    output_path = Path(output_dir)
    
    # 创建目录
    raw_dir = output_path / 'raw'
    wiki_dir = output_path / 'wiki'
    for d in [raw_dir / 'emails' / '2026', raw_dir / 'threads', wiki_dir / 'qa', wiki_dir / 'categories']:
        d.mkdir(parents=True, exist_ok=True)
    
    # 保存原始邮件索引
    email_index = []
    for email in emails:
        email_index.append({
            'id': email['id'],
            'subject': email['subject'],
            'sender': email['sender_email'],
            'role': email['sender_role'],
            'time': email['received_time'],
            'source': email.get('source', 'unknown')
        })
    
    with open(raw_dir / 'index.json', 'w', encoding='utf-8') as f:
        json.dump({
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'total_emails': len(emails),
            'emails': email_index
        }, f, ensure_ascii=False, indent=2)
    
    # 保存 wiki QA
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
            'history': [{'action': 'created', 'timestamp': datetime.now().isoformat(), 'note': '180天混合采集'}]
        }
        
        with open(wiki_dir / 'qa' / f"{qa['id']}.json", 'w', encoding='utf-8') as f:
            json.dump(wiki_qa, f, ensure_ascii=False, indent=2)
    
    # 分类索引
    cat_count = defaultdict(list)
    for qa in qa_pairs:
        cat_count[qa.get('category', '其他')].append(qa['id'])
    
    for cat, qa_ids in cat_count.items():
        cat_path = wiki_dir / 'categories' / cat
        cat_path.mkdir(exist_ok=True)
        with open(cat_path / 'index.json', 'w', encoding='utf-8') as f:
            json.dump({'category': cat, 'total': len(qa_ids), 'qa_ids': qa_ids}, f, ensure_ascii=False, indent=2)
    
    # 搜索索引
    search_records = [{
        'id': qa['id'],
        'category': qa.get('category', '其他'),
        'question_summary': qa['question']['text'][:100],
        'answer_summary': qa['answer']['text'][:100]
    } for qa in qa_pairs]
    
    with open(wiki_dir / 'search_index.json', 'w', encoding='utf-8') as f:
        json.dump({'version': '1.0', 'total': len(search_records), 'records': search_records}, f, ensure_ascii=False, indent=2)
    
    print(f"  完成: {len(emails)} 封邮件, {len(qa_pairs)} 个问答对")

def main():
    print("=" * 60)
    print("AllegroSupport 180天混合采集")
    print("=" * 60)
    
    # 1. 加载现有数据
    existing_file = Path(__file__).parent.parent.parent / '_allegro_emails.json'
    if not existing_file.exists():
        print(f"错误: 找不到现有数据文件 {existing_file}")
        return
    
    existing_emails = load_existing_data(existing_file)
    
    # 2. Outlook 增量采集
    incremental_emails = fetch_from_outlook(days=180)
    
    # 3. 合并
    all_emails = merge_emails(existing_emails, incremental_emails)
    
    # 4. 提取问答对
    conversations = group_by_conversation(all_emails)
    qa_pairs = extract_qa_pairs(conversations)
    
    if not qa_pairs:
        print("\n未能提取问答对，请检查数据")
        return
    
    # 5. 分类
    qa_pairs = categorize_qa(qa_pairs)
    
    # 统计
    cat_stats = defaultdict(int)
    for qa in qa_pairs:
        cat_stats[qa.get('category', '其他')] += 1
    
    print("\n分类统计:")
    for cat, count in sorted(cat_stats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 个")
    
    # 6. 保存
    output_dir = Path(__file__).parent.parent / 'data_180days_hybrid'
    save_to_binary_structure(all_emails, qa_pairs, output_dir)
    
    # 7. 标准格式
    standard = {
        'total': len(qa_pairs),
        'categories': dict(cat_stats),
        'qa_pairs': qa_pairs,
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'days_covered': 180,
            'source': 'hybrid (existing + outlook)'
        }
    }
    with open(output_dir / 'qa_pairs_180days.json', 'w', encoding='utf-8') as f:
        json.dump(standard, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 完成！输出目录: {output_dir}/")

if __name__ == '__main__':
    main()
