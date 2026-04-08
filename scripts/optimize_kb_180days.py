#!/usr/bin/env python3
"""
优化180天知识库数据：
1. 分类优化 - 基于body + subject重新分类
2. 质量审核 - 过滤低质量数据
3. 合并旧数据 - 标记已审核的71条高质量QA
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# IT 同事白名单
SUPPORT_SENDERS = {
    'kieranji@culines.com',
    'joanneding@culines.com',
    'catherinekang@culines.com'
}

# 优化后的分类关键词（基于主题词分析）
CATEGORIES = {
    '订舱操作': [
        'booking', '订舱', 'so number', 'slot', 'container', 'vd move', 'vessel',
        'etb', 'eta', 'voyage', 'bkd', 'shipping order'
    ],
    '提单操作': [
        'bl', 'bill of lading', '提单', 'manifest', 'bl number', 'release',
        'telex release', 'swb', 'draft bl'
    ],
    '报关操作': [
        'customs', '报关', 'declaration', 'clearance', 'hs code', 'ciq'
    ],
    '费用相关': [
        'invoice', '费用', 'payment', 'charge', 'cost', 'debit note',
        'credit note', 'soa', '账单', '付款'
    ],
    '系统问题': [
        'error', 'bug', 'system', 'issue', 'failed', 'problem', 'cannot',
        '无法', '错误', '问题', '故障', 'not working'
    ],
    '数据修改': [
        'update', 'modify', 'change', 'edit', '数据', '修改', '变更',
        'amendment', 'correct', 'revise'
    ],
    '权限申请': [
        'access', '权限', 'account', 'login', 'password', '用户', '账号',
        'authorization', 'role', 'register'
    ],
    '其他': []
}


def extract_email_from_sender(sender_str):
    """从发件人字符串提取邮箱"""
    if not sender_str:
        return ''
    
    # 尝试匹配 <email> 格式
    match = re.search(r'<(.+?)>', sender_str)
    if match:
        return match.group(1).lower()
    
    # 尝试匹配邮箱格式
    match = re.search(r'[\w\.-]+@[\w\.-]+', sender_str)
    if match:
        return match.group(0).lower()
    
    # Exchange格式: /o=exchangelabs/ou=.../cn=...
    if '/o=' in sender_str:
        return sender_str
    
    return sender_str.lower()


def load_source_data():
    """加载原始数据源"""
    print("=== 加载原始数据 ===")
    
    source_path = Path('_allegro_emails.json')
    with open(source_path, encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"  IT回复: {len(data.get('it_replies', []))} 封")
    print(f"  用户问题: {len(data.get('user_questions', []))} 封")
    
    return data


def extract_qa_pairs_with_body(source_data):
    """提取问答对（保留body）"""
    print("\n=== 提取问答对（保留body）===")
    
    it_replies = source_data.get('it_replies', [])
    user_questions = source_data.get('user_questions', [])
    
    # 按日期分组
    by_date = defaultdict(lambda: {'questions': [], 'replies': []})
    
    for q in user_questions:
        date = q.get('date', '')[:10]  # YYYY-MM-DD
        by_date[date]['questions'].append(q)
    
    for r in it_replies:
        date = r.get('date', '')[:10]
        by_date[date]['replies'].append(r)
    
    # 匹配问答对
    qa_pairs = []
    qa_id = 1
    
    for date in sorted(by_date.keys()):
        day_data = by_date[date]
        
        # 简单匹配：每个问题对应最近的回复
        for i, question in enumerate(day_data['questions']):
            if i < len(day_data['replies']):
                reply = day_data['replies'][i]
                
                qa = {
                    'id': f'qa_{qa_id}',
                    'subject': question.get('subject', ''),
                    'question': {
                        'text': question.get('body', ''),
                        'sender': question.get('sender', ''),
                        'sender_email': extract_email_from_sender(question.get('sender_email', '')),
                        'time': question.get('time', '')
                    },
                    'answer': {
                        'text': reply.get('body', ''),
                        'responder': reply.get('sender', ''),
                        'responder_email': extract_email_from_sender(reply.get('sender_email', '')),
                        'time': reply.get('time', '')
                    },
                    'date': date,
                    'category': '其他',  # 待分类
                    'quality_score': 0  # 待评分
                }
                
                qa_pairs.append(qa)
                qa_id += 1
    
    print(f"  提取到 {len(qa_pairs)} 个问答对")
    return qa_pairs


def categorize_qa(qa_pairs):
    """分类优化 - 基于body + subject"""
    print("\n=== 分类优化 ===")
    
    cat_stats = defaultdict(int)
    
    for qa in qa_pairs:
        # 合并主题和正文
        text = ' '.join([
            qa['subject'],
            qa['question']['text'],
            qa['answer']['text']
        ]).lower()
        
        # 匹配分类
        assigned = False
        for cat, keywords in CATEGORIES.items():
            if cat == '其他':
                continue
            
            # 计算匹配度
            matched_keywords = sum(1 for kw in keywords if kw.lower() in text)
            if matched_keywords > 0:
                qa['category'] = cat
                qa['matched_keywords'] = matched_keywords
                cat_stats[cat] += 1
                assigned = True
                break
        
        if not assigned:
            qa['category'] = '其他'
            cat_stats['其他'] += 1
    
    # 打印分类统计
    print("  分类统计:")
    for cat, count in sorted(cat_stats.items(), key=lambda x: -x[1]):
        pct = count * 100 / len(qa_pairs)
        print(f"    {cat}: {count} ({pct:.1f}%)")
    
    return qa_pairs


def quality_review(qa_pairs):
    """质量审核"""
    print("\n=== 质量审核 ===")
    
    filtered_qa = []
    rejected = defaultdict(int)
    
    for qa in qa_pairs:
        q_text = qa['question']['text']
        a_text = qa['answer']['text']
        subject = qa['subject']
        
        # 计算质量分数
        score = 0
        reasons = []
        
        # 1. 内容完整性
        if len(q_text) < 20:
            reasons.append('问题内容<20字符')
            rejected['问题内容过短'] += 1
        elif len(q_text) >= 50:
            score += 2
        
        if len(a_text) < 20:
            reasons.append('回答内容<20字符')
            rejected['回答内容过短'] += 1
        elif len(a_text) >= 100:
            score += 2
        
        # 2. 主题相关性
        if 'allegro' in subject.lower() or 'allegro' in q_text.lower():
            score += 1
        else:
            reasons.append('主题不相关Allegro')
            rejected['主题不相关'] += 1
        
        # 3. 回答有效性
        if any(sender in qa['answer']['responder_email'].lower() for sender in SUPPORT_SENDERS):
            score += 2
        else:
            reasons.append('非IT同事回复')
            rejected['非IT回复'] += 1
        
        # 4. 内容质量
        if 'thank' in a_text.lower() or 'thanks' in a_text.lower():
            score += 1
        if 'please' in a_text.lower():
            score += 1
        
        qa['quality_score'] = score
        qa['quality_reasons'] = reasons
        
        # 过滤低质量
        if score >= 3 and len(q_text) >= 10 and len(a_text) >= 10:
            filtered_qa.append(qa)
        else:
            rejected['总分<3或内容过短'] += 1
    
    print(f"  原始: {len(qa_pairs)} 条")
    print(f"  过滤: {len(qa_pairs) - len(filtered_qa)} 条")
    print(f"  保留: {len(filtered_qa)} 条")
    print(f"  过滤原因:")
    for reason, count in sorted(rejected.items(), key=lambda x: -x[1]):
        print(f"    {reason}: {count}")
    
    return filtered_qa


def load_old_verified_data():
    """加载旧的71条已审核数据"""
    print("\n=== 加载旧数据（已审核）===")
    
    old_path = Path('allegrosupport-kb/data/qa_pairs.json')
    if not old_path.exists():
        print("  旧数据文件不存在")
        return []
    
    with open(old_path, encoding='utf-8') as f:
        old_data = json.load(f)
    
    old_qa = old_data.get('qa_pairs', [])
    print(f"  加载 {len(old_qa)} 条已审核数据")
    
    # 标记为已审核
    for qa in old_qa:
        qa['verified'] = True
        qa['verified_date'] = '2026-04-07'
    
    return old_qa


def merge_data(new_qa, old_qa):
    """合并新旧数据"""
    print("\n=== 合并数据 ===")
    
    # 按主题去重
    subject_set = set()
    merged_qa = []
    
    # 优先保留已审核数据
    for qa in old_qa:
        subject_key = qa.get('subject', '').lower().strip()
        if subject_key and subject_key not in subject_set:
            merged_qa.append(qa)
            subject_set.add(subject_key)
    
    print(f"  已审核数据: {len(merged_qa)} 条")
    
    # 添加新数据
    new_count = 0
    for qa in new_qa:
        subject_key = qa.get('subject', '').lower().strip()
        if subject_key and subject_key not in subject_set:
            qa['verified'] = False
            merged_qa.append(qa)
            subject_set.add(subject_key)
            new_count += 1
    
    print(f"  新增数据: {new_count} 条")
    print(f"  合并后: {len(merged_qa)} 条")
    
    # 统计
    verified_count = sum(1 for qa in merged_qa if qa.get('verified'))
    print(f"  已审核: {verified_count} 条")
    print(f"  待审核: {len(merged_qa) - verified_count} 条")
    
    return merged_qa


def save_optimized_data(qa_pairs):
    """保存优化后的数据"""
    print("\n=== 保存数据 ===")
    
    output_dir = Path('allegrosupport-kb/data_180days_optimized')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 统计
    cat_stats = defaultdict(int)
    verified_count = 0
    for qa in qa_pairs:
        cat_stats[qa['category']] += 1
        if qa.get('verified'):
            verified_count += 1
    
    # 保存主文件
    output_data = {
        'total': len(qa_pairs),
        'verified': verified_count,
        'pending_review': len(qa_pairs) - verified_count,
        'categories': dict(cat_stats),
        'generated_at': datetime.now().isoformat(),
        'qa_pairs': qa_pairs
    }
    
    output_file = output_dir / 'qa_pairs_optimized.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"  保存到: {output_file}")
    
    # 保存分类索引
    for cat in cat_stats.keys():
        cat_dir = output_dir / 'categories' / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        
        cat_qa = [qa for qa in qa_pairs if qa['category'] == cat]
        cat_file = cat_dir / 'index.json'
        
        with open(cat_file, 'w', encoding='utf-8') as f:
            json.dump({
                'category': cat,
                'count': len(cat_qa),
                'qa_pairs': cat_qa
            }, f, ensure_ascii=False, indent=2)
    
    print(f"  分类索引: {len(cat_stats)} 个")
    
    # 保存质量报告
    quality_report = {
        'total': len(qa_pairs),
        'avg_quality_score': sum(qa.get('quality_score', 0) for qa in qa_pairs) / len(qa_pairs) if qa_pairs else 0,
        'verified': verified_count,
        'by_category': dict(cat_stats),
        'by_score': defaultdict(int)
    }
    
    for qa in qa_pairs:
        score = qa.get('quality_score', 0)
        quality_report['by_score'][str(score)] += 1
    
    quality_file = output_dir / 'quality_report.json'
    with open(quality_file, 'w', encoding='utf-8') as f:
        json.dump(quality_report, f, ensure_ascii=False, indent=2)
    
    print(f"  质量报告: {quality_file}")


def main():
    print("="*60)
    print("180天知识库优化")
    print("="*60)
    
    # 1. 加载原始数据
    source_data = load_source_data()
    
    # 2. 提取问答对（保留body）
    qa_pairs = extract_qa_pairs_with_body(source_data)
    
    # 3. 分类优化
    qa_pairs = categorize_qa(qa_pairs)
    
    # 4. 质量审核
    filtered_qa = quality_review(qa_pairs)
    
    # 5. 加载旧的已审核数据
    old_qa = load_old_verified_data()
    
    # 6. 合并数据
    merged_qa = merge_data(filtered_qa, old_qa)
    
    # 7. 保存
    save_optimized_data(merged_qa)
    
    print("\n" + "="*60)
    print("优化完成！")
    print("="*60)


if __name__ == '__main__':
    main()
