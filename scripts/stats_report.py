# -*- coding: utf-8 -*-
"""
生成问答对统计分析报告
"""

import sys
import io
import json
from collections import defaultdict, Counter
from datetime import datetime

# 设置 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    # 读取数据
    with open('allegrosupport-kb/data/qa_pairs.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    qa_pairs = data['qa_pairs']
    
    print("=" * 80)
    print("AllegroSupport 邮件知识库 - 统计分析报告")
    print("=" * 80)
    print()
    
    # 1. 基本统计
    print("【一、数据概览】")
    print(f"  - 问答对总数: {data['total']}")
    print(f"  - 时间范围: 最近 90 天")
    print(f"  - 生成时间: {data['generated_at']}")
    print()
    
    # 2. 问题分类统计
    print("【二、问题分类统计】")
    for cat, count in sorted(data['categories'].items(), key=lambda x: x[1], reverse=True):
        percentage = count / data['total'] * 100
        bar = '█' * int(percentage / 5)
        print(f"  {cat:12} {count:3} 个 ({percentage:5.1f}%) {bar}")
    print()
    
    # 3. IT 支持人员统计
    print("【三、IT 支持人员回复统计】")
    responders = Counter(qa['answer']['responder'] for qa in qa_pairs)
    for responder, count in responders.most_common():
        percentage = count / data['total'] * 100
        print(f"  {responder:30} {count:3} 次 ({percentage:5.1f}%)")
    print()
    
    # 4. 提问人统计（Top 10）
    print("【四、提问人统计（Top 10）】")
    askers = Counter(qa['question']['sender'] for qa in qa_pairs)
    for asker, count in askers.most_common(10):
        print(f"  {asker:40} {count:3} 次")
    print()
    
    # 5. 时间分布
    print("【五、提问时间分布】")
    hourly_dist = defaultdict(int)
    for qa in qa_pairs:
        time_str = qa['question']['time']
        # 格式是 "04-03 17:27"，提取小时部分
        time_part = time_str.split(' ')[1] if ' ' in time_str else time_str
        hour = int(time_part.split(':')[0])
        hourly_dist[hour] += 1
    
    print("  时间段     数量  分布图")
    for hour in sorted(hourly_dist.keys()):
        count = hourly_dist[hour]
        bar = '▓' * count
        print(f"  {hour:02d}:00-{hour:02d}:59  {count:3}   {bar}")
    print()
    
    # 6. 按分类展示示例
    print("【六、各分类示例问题】")
    print()
    
    category_examples = defaultdict(list)
    for qa in qa_pairs:
        category_examples[qa['category']].append(qa)
    
    for category in sorted(data['categories'].keys(), key=lambda x: data['categories'][x], reverse=True):
        examples = category_examples[category][:2]  # 每类最多 2 个示例
        
        print(f"  【{category}】({data['categories'][category]} 个)")
        for i, qa in enumerate(examples, 1):
            question_text = qa['question']['text']
            # 提取前 100 个字符
            short_question = question_text[:100].replace('\r\n', ' ').strip()
            if len(question_text) > 100:
                short_question += '...'
            
            print(f"    {i}. {short_question}")
            print(f"       回复人: {qa['answer']['responder']}")
        print()
    
    # 7. 数据质量分析
    print("【七、数据质量分析】")
    
    # 统计包含附件的问答对
    with_attachment = sum(1 for qa in qa_pairs if qa['metadata']['has_attachment'])
    print(f"  - 包含附件的问答对: {with_attachment} 个 ({with_attachment/data['total']*100:.1f}%)")
    
    # 统计问题长度
    question_lengths = [len(qa['question']['text']) for qa in qa_pairs]
    avg_length = sum(question_lengths) / len(question_lengths)
    print(f"  - 平均问题长度: {avg_length:.0f} 字符")
    print(f"  - 最短问题: {min(question_lengths)} 字符")
    print(f"  - 最长问题: {max(question_lengths)} 字符")
    
    # 统计答案长度
    answer_lengths = [len(qa['answer']['text']) for qa in qa_pairs]
    avg_answer_length = sum(answer_lengths) / len(answer_lengths)
    print(f"  - 平均答案长度: {avg_answer_length:.0f} 字符")
    print()
    
    # 8. 知识库价值评估
    print("【八、知识库价值评估】")
    print(f"  ✅ 已积累 {data['total']} 个问答对")
    print(f"  ✅ 覆盖 {len(data['categories'])} 个业务场景")
    print(f"  ✅ 涉及 {len(askers)} 个提问人")
    print(f"  ✅ 由 {len(responders)} 位 IT 同事提供支持")
    print()
    
    print("【九、下一步建议】")
    print("  1. 继续积累数据（建议达到 100+ 问答对）")
    print("  2. 接入向量数据库实现语义检索")
    print("  3. 构建自动回复系统")
    print("  4. 定期更新和维护知识库")
    print()
    
    print("=" * 80)

if __name__ == "__main__":
    main()
