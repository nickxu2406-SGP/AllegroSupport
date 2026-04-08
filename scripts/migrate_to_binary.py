#!/usr/bin/env python3
"""
AllegroSupport KB 二元分离迁移脚本
将 flat qa_pairs.json 迁移到 raw/ + wiki/ 二元分离结构

用法:
    python migrate_to_binary.py [--input ../data/qa_pairs.json] [--output .]
"""

import json
import os
import shutil
import argparse
from datetime import datetime
from pathlib import Path

UTC_OFFSET = 8  # 北京时间 UTC+8


def bj_now():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_time(time_str):
    """
    解析 qa_pairs.json 中的 time 字段 (如 '03-31 16:51')
    假设年份为 2026
    """
    try:
        dt = datetime.strptime(f"2026-{time_str}", "%Y-%m-%d %H:%M")
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return time_str


def extract_keywords(text, category=None):
    """从文本中提取关键词（简化版，不依赖外部库）"""
    # 常见关键词列表
    booking_kw = ['booking', 'VD', 'route', 'container', 'vessel', 'discharge',
                  'POL', 'POD', 'DEL', 'booking confirmation', 'booking note']
    customs_kw = ['customs', 'declaration', '报关', '清关', 'HS code', 'D/O']
    bl_kw = ['BL', 'bill of lading', '提单', 'MBL', 'HBL', 'telex release']
    system_kw = ['system', 'error', 'bug', 'login', 'password', 'Allegro', 'permission']

    text_lower = text.lower()
    found = []
    for kw in booking_kw + customs_kw + bl_kw + system_kw:
        if kw.lower() in text_lower:
            found.append(kw)

    if category:
        found.append(category)

    return list(set(found))[:10]


def extract_summary(text, max_len=120):
    """生成摘要"""
    # 去掉邮件签名和引用的常见行
    lines = text.split('\n')
    meaningful = []
    skip_patterns = ['regards', 'best', 'thanks', 'mobile', 'e-mail', 'tel:',
                     '发件人', '收件人', '抄送', '发送时间', 'from:', 'to:', 'date:',
                     '>', '-----', '====', '签', '德', '商船', 'www.']

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(p in line.lower() for p in skip_patterns):
            continue
        meaningful.append(line)
        if len(' '.join(meaningful)) > max_len:
            break

    summary = ' '.join(meaningful)[:max_len]
    if len(' '.join(meaningful)) > max_len:
        summary += '...'
    return summary


def build_email_record(qa):
    """从单条 QA 构建虚拟的原始邮件记录（用于 raw/ 层）"""
    question = qa['question']
    answer = qa['answer']

    q_time = parse_time(question.get('time', ''))
    a_time = parse_time(answer.get('time', ''))

    # 推断年月
    year_month = q_time[5:7] if len(q_time) > 7 else '03'

    email_id_prefix = f"migrated_{qa['id']}"

    # question 邮件
    q_email = {
        "id": f"{email_id_prefix}_q",
        "conversationId": f"thread_{qa['id']}",
        "internetMessageId": f"<migrated-{qa['id']}-q@allegro-support>",
        "subject": question.get('sender_email', 'Unknown Subject'),
        "sender": {
            "emailAddress": {
                "name": question.get('sender', ''),
                "address": question.get('sender_email', '')
            }
        },
        "toRecipients": [{"emailAddress": {"name": "Allegro Support", "address": "allegrosupport@culines.com"}}],
        "ccRecipients": [],
        "receivedDateTime": q_time,
        "sentDateTime": q_time,
        "body": {"contentType": "text", "content": question.get('text', '')},
        "hasAttachments": qa.get('metadata', {}).get('has_attachment', False),
        "importance": "normal" if not qa.get('metadata', {}).get('importance') else "high",
        "_migrated_from_qa_id": qa['id'],
        "_migrated_at": bj_now()
    }

    # answer 邮件
    a_email = {
        "id": f"{email_id_prefix}_a",
        "conversationId": f"thread_{qa['id']}",
        "internetMessageId": f"<migrated-{qa['id']}-a@allegro-support>",
        "subject": f"Re: {question.get('sender_email', 'Unknown Subject')}",
        "sender": {
            "emailAddress": {
                "name": answer.get('responder', ''),
                "address": f"responder_{qa['id']}@culines.com"
            }
        },
        "toRecipients": [{"emailAddress": {"name": question.get('sender', ''), "address": question.get('sender_email', '')}}],
        "ccRecipients": [],
        "receivedDateTime": a_time,
        "sentDateTime": a_time,
        "body": {"contentType": "text", "content": answer.get('text', '')},
        "hasAttachments": False,
        "importance": "normal",
        "_migrated_from_qa_id": qa['id'],
        "_migrated_at": bj_now()
    }

    return q_email, a_email, year_month


def build_thread_record(qa, q_email, a_email):
    """构建线程记录"""
    q_time = parse_time(qa['question'].get('time', ''))
    a_time = parse_time(qa['answer'].get('time', ''))
    # 从时间戳提取年月文件夹
    q_month = q_time[5:7] if len(q_time) > 7 else '03'
    a_month = a_time[5:7] if len(a_time) > 7 else '03'

    return {
        "conversation_id": f"thread_{qa['id']}",
        "subject": qa.get('subject', ''),
        "emails": [
            {"$ref": f"../emails/2026/{q_month}/{q_email['id']}.json"},
            {"$ref": f"../emails/2026/{a_month}/{a_email['id']}.json"}
        ],
        "participants": [
            {
                "name": qa['question'].get('sender', ''),
                "email": qa['question'].get('sender_email', ''),
                "role": "external"
            },
            {
                "name": qa['answer'].get('responder', ''),
                "email": f"responder_{qa['id']}@culines.com",
                "role": "support"
            }
        ],
        "first_email_at": q_time,
        "last_email_at": a_time,
        "email_count": 2,
        "_migrated_from_qa_id": qa['id'],
        "_migrated_at": bj_now()
    }


def build_wiki_qa(qa):
    """构建 wiki/qa/{id}.json"""
    question = qa['question']
    answer = qa['answer']
    q_time = parse_time(question.get('time', ''))
    a_time = parse_time(answer.get('time', ''))
    qa_id = qa['id']

    question_text = question.get('text', '')
    answer_text = answer.get('text', '')

    return {
        "id": qa_id,
        "version": 1,

        "question": {
            "text": question_text,
            "original_email_id": f"migrated_{qa_id}_q",
            "sender_name": question.get('sender', ''),
            "sender_email": question.get('sender_email', ''),
            "sent_at": q_time,
            "summary": extract_summary(question_text, max_len=100),
            "keywords": extract_keywords(question_text, qa.get('category', ''))
        },

        "answer": {
            "text": answer_text,
            "original_email_id": f"migrated_{qa_id}_a",
            "responder_name": answer.get('responder', ''),
            "responder_email": f"responder_{qa_id}@culines.com",
            "sent_at": a_time,
            "summary": extract_summary(answer_text, max_len=80),
            "keywords": extract_keywords(answer_text, qa.get('category', ''))
        },

        "thread": {
            "id": f"thread_{qa_id}",
            "path": f"../raw/threads/thread_{qa_id}.json",
            "note": "原始线程记录（迁移数据，邮件内容见 question.original_email_id）"
        },

        "classification": {
            "category": qa.get('category', '其他'),
            "subcategory": "",
            "related_system": "Allegro",
            "related_module": "",
            "tags": []
        },

        "quality": {
            "confidence_score": 0.85,
            "is_verified": False,
            "verified_by": None,
            "verified_at": None,
            "helpful_count": 0,
            "escalation_count": 0
        },

        "source": {
            "extracted_from": f"qa_pairs.json (flat)",
            "extracted_at": bj_now(),
            "extracted_by": "migrate_to_binary.py v1.0",
            "original_subject": qa.get('subject', '')
        },

        "history": [
            {
                "action": "migrate",
                "at": bj_now(),
                "by": "migrate_to_binary.py",
                "note": "从 flat qa_pairs.json 迁移到二元分离结构"
            }
        ]
    }


def main():
    parser = argparse.ArgumentParser(description='AllegroSupport KB 二元分离迁移')
    parser.add_argument('--input', default='../data/qa_pairs.json',
                        help='输入文件路径 (qa_pairs.json)')
    parser.add_argument('--output', default='.',
                        help='输出根目录 (allegrosupport-kb/)')
    args = parser.parse_args()

    # 读取输入
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    qa_pairs = data['qa_pairs']
    base_dir = Path(args.output)

    # 创建目录
    raw_emails_dir = base_dir / 'raw' / 'emails'
    raw_threads_dir = base_dir / 'raw' / 'threads'
    wiki_qa_dir = base_dir / 'wiki' / 'qa'
    wiki_cat_dir = base_dir / 'wiki' / 'categories'

    for d in [raw_emails_dir, raw_threads_dir, wiki_qa_dir, wiki_cat_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"开始迁移 {len(qa_pairs)} 条 QA...")

    # 统计
    raw_index = {
        "version": "1.0",
        "generated_at": bj_now(),
        "total_emails": 0,
        "total_threads": 0,
        "emails_by_month": {},
        "by_id": {}
    }

    wiki_index = {
        "version": "1.0",
        "generated_at": bj_now(),
        "total": len(qa_pairs),
        "records": []
    }

    category_index = {}  # category -> qa_ids
    processed = 0

    for qa in qa_pairs:
        qa_id = qa['id']
        question = qa['question']
        answer = qa['answer']

        q_time = parse_time(question.get('time', ''))
        month_folder = q_time[5:7] if len(q_time) > 7 else '03'
        year_folder = '2026'

        # 构建 raw 记录
        q_email, a_email, month_folder = build_email_record(qa)
        q_email_id = q_email['id']
        a_email_id = a_email['id']

        # 写入原始邮件
        email_dir = raw_emails_dir / year_folder / month_folder
        email_dir.mkdir(parents=True, exist_ok=True)

        with open(email_dir / f'{q_email_id}.json', 'w', encoding='utf-8') as f:
            json.dump(q_email, f, ensure_ascii=False, indent=2)
        with open(email_dir / f'{a_email_id}.json', 'w', encoding='utf-8') as f:
            json.dump(a_email, f, ensure_ascii=False, indent=2)

        # 写入线程
        thread = build_thread_record(qa, q_email, a_email)
        with open(raw_threads_dir / f'thread_{qa_id}.json', 'w', encoding='utf-8') as f:
            json.dump(thread, f, ensure_ascii=False, indent=2)

        # 更新 raw 索引
        month_key = f"{year_folder}-{month_folder}"
        if month_key not in raw_index['emails_by_month']:
            raw_index['emails_by_month'][month_key] = {"count": 0, "emails": []}
        raw_index['emails_by_month'][month_key]["count"] += 2
        raw_index['emails_by_month'][month_key]["emails"].extend([q_email_id, a_email_id])
        raw_index['by_id'][q_email_id] = {
            "path": f"emails/{year_folder}/{month_folder}/{q_email_id}.json",
            "thread_id": f"thread_{qa_id}"
        }
        raw_index['by_id'][a_email_id] = {
            "path": f"emails/{year_folder}/{month_folder}/{a_email_id}.json",
            "thread_id": f"thread_{qa_id}"
        }
        raw_index['total_emails'] += 2
        raw_index['total_threads'] += 1

        # 构建 wiki QA
        wiki_qa = build_wiki_qa(qa)
        with open(wiki_qa_dir / f'{qa_id}.json', 'w', encoding='utf-8') as f:
            json.dump(wiki_qa, f, ensure_ascii=False, indent=2)

        # 更新 wiki 索引
        wiki_record = {
            "id": qa_id,
            "path": f"qa/{qa_id}.json",
            "category": qa.get('category', '其他'),
            "tags": [],
            "question_keywords": wiki_qa['question']['keywords'],
            "question_summary": wiki_qa['question']['summary'],
            "answer_summary": wiki_qa['answer']['summary'],
            "confidence": 0.85,
            "is_verified": False
        }
        wiki_index['records'].append(wiki_record)

        # 更新分类索引
        cat = qa.get('category', '其他')
        if cat not in category_index:
            category_index[cat] = []
        category_index[cat].append(qa_id)

        processed += 1
        if processed % 10 == 0:
            print(f"  已处理 {processed}/{len(qa_pairs)}...")

    # 写入索引文件
    # raw/index.json
    with open(base_dir / 'raw' / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(raw_index, f, ensure_ascii=False, indent=2)

    # wiki/index.json
    with open(base_dir / 'wiki' / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(wiki_index, f, ensure_ascii=False, indent=2)

    # wiki/search_index.json（用于 AI 直读）
    with open(base_dir / 'wiki' / 'search_index.json', 'w', encoding='utf-8') as f:
        json.dump(wiki_index, f, ensure_ascii=False, indent=2)

    # wiki/categories/{cat}/index.json
    for cat, qa_ids in category_index.items():
        cat_dir = wiki_cat_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        with open(cat_dir / 'index.json', 'w', encoding='utf-8') as f:
            json.dump({
                "category": cat,
                "total": len(qa_ids),
                "qa_ids": qa_ids,
                "last_updated": bj_now()
            }, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 50)
    print("迁移完成！")
    print("=" * 50)
    print(f"raw/emails/         → {raw_index['total_emails']} 封邮件")
    print(f"raw/threads/        → {raw_index['total_threads']} 个线程")
    print(f"wiki/qa/            → {processed} 条 QA")
    print(f"wiki/categories/   → {len(category_index)} 个分类")
    print()
    print("分类分布:")
    for cat, ids in sorted(category_index.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(ids)} 条")
    print()
    print("文件清单:")
    for p in sorted((base_dir / 'raw').rglob('*.json')):
        print(f"  {p.relative_to(base_dir)}")
    for p in sorted((base_dir / 'wiki').rglob('*.json')):
        print(f"  {p.relative_to(base_dir)}")


if __name__ == '__main__':
    main()
