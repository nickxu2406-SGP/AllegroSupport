# -*- coding: utf-8 -*-
"""
简化版演示脚本
无需安装额外依赖，使用关键词匹配演示检索功能
"""

import sys
import io
import json
import re
from typing import List, Dict, Tuple

# 设置 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class SimpleKnowledgeBase:
    """简化的知识库（基于关键词匹配）"""
    
    def __init__(self, json_file: str = "allegrosupport-kb/data/qa_pairs.json"):
        """初始化知识库"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.qa_pairs = data['qa_pairs']
        self.categories = data['categories']
        
        # 构建关键词索引
        self.keyword_index = {}
        for qa in self.qa_pairs:
            keywords = self._extract_keywords(qa['question']['text'] + ' ' + qa['answer']['text'])
            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(qa['id'])
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 分词
        words = text.lower().split()
        
        # 过滤停用词
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                     'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                     'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
                     'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
                     'dear', 'thanks', 'thank', 'please', 'best', 'regards', 'kind'}
        
        keywords = [w for w in words if len(w) > 2 and w not in stopwords]
        
        return list(set(keywords))
    
    def search(self, query: str, n_results: int = 5, category_filter: str = None) -> List[Dict]:
        """
        搜索问答对
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            category_filter: 分类过滤
        
        Returns:
            搜索结果列表
        """
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        
        # 计算每个问答对的匹配分数
        scores = []
        for qa in self.qa_pairs:
            # 分类过滤
            if category_filter and qa['category'] != category_filter:
                continue
            
            # 计算关键词匹配分数
            qa_keywords = self._extract_keywords(qa['question']['text'] + ' ' + qa['answer']['text'])
            common_keywords = set(query_keywords) & set(qa_keywords)
            
            if common_keywords:
                score = len(common_keywords) / len(query_keywords)
                scores.append((qa, score, common_keywords))
        
        # 按分数排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 返回前 N 个结果
        return scores[:n_results]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_qa_pairs': len(self.qa_pairs),
            'total_categories': len(self.categories),
            'categories': self.categories
        }


def demo():
    """演示搜索功能"""
    
    print("=" * 80)
    print("AllegroSupport 知识库 - 简化版演示")
    print("=" * 80)
    print()
    
    # 初始化知识库
    kb = SimpleKnowledgeBase()
    stats = kb.get_stats()
    
    print(f"[统计]")
    print(f"  问答对总数: {stats['total_qa_pairs']}")
    print(f"  问题分类: {stats['total_categories']}")
    print()
    
    # 演示搜索
    print("=" * 80)
    print("语义搜索演示（关键词匹配）")
    print("=" * 80)
    
    test_queries = [
        "订舱修改",
        "提单错误",
        "系统权限",
        "报关问题",
        "BL code removal",
        "storage waiver",
    ]
    
    for query in test_queries:
        print(f"\n【查询】{query}")
        print("-" * 80)
        
        results = kb.search(query, n_results=2)
        
        if results:
            for i, (qa, score, keywords) in enumerate(results, 1):
                print(f"\n  [{i}] 匹配度: {score:.0%}")
                print(f"  匹配关键词: {', '.join(keywords)}")
                print(f"  分类: {qa['category']}")
                print(f"  主题: {qa['subject']}")
                print(f"  问题: {qa['question']['text'][:100]}...")
                print(f"  答案: {qa['answer']['text'][:100]}...")
        else:
            print("  未找到匹配结果")
        
        print()
    
    # 交互式搜索
    print("=" * 80)
    print("交互式搜索（输入 'quit' 退出）")
    print("=" * 80)
    
    while True:
        try:
            query = input("\n请输入查询内容: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n[退出] 感谢使用！")
                break
            
            if not query:
                continue
            
            results = kb.search(query, n_results=3)
            
            if results:
                print(f"\n找到 {len(results)} 个相关结果：")
                for i, (qa, score, keywords) in enumerate(results, 1):
                    print(f"\n  [{i}] 匹配度: {score:.0%}")
                    print(f"  分类: {qa['category']}")
                    print(f"  主题: {qa['subject']}")
                    print(f"  问题: {qa['question']['text'][:150]}...")
                    print(f"  答案: {qa['answer']['text'][:150]}...")
            else:
                print("\n  未找到匹配结果，请尝试其他关键词")
        
        except (EOFError, KeyboardInterrupt):
            print("\n\n[退出] 感谢使用！")
            break


if __name__ == "__main__":
    demo()
