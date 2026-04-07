# -*- coding: utf-8 -*-
"""
向量检索系统
使用 ChromaDB 构建知识库向量索引
"""

import sys
import io
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 设置 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 延迟导入（避免缺少依赖时报错）
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[警告] ChromaDB 未安装，请运行: pip install chromadb==0.4.22")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("[警告] sentence-transformers 未安装，请运行: pip install sentence-transformers==2.2.2")


class VectorKnowledgeBase:
    """向量知识库"""
    
    def __init__(self, persist_directory: str = "../data/chroma_db"):
        """
        初始化向量知识库
        
        Args:
            persist_directory: 向量数据库持久化目录
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB 未安装")
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.persist_directory))
        
        # 初始化嵌入模型（使用多语言模型）
        if EMBEDDINGS_AVAILABLE:
            print("[初始化] 加载嵌入模型...")
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("[完成] 模型加载完成")
        else:
            self.embedding_model = None
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="allegrosupport_qa",
            metadata={"description": "Allegro 系统支持问答对"}
        )
    
    def load_qa_pairs(self, json_file: str = "../data/qa_pairs.json") -> List[Dict]:
        """加载问答对数据"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['qa_pairs']
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        将文本转换为向量
        
        Args:
            texts: 文本列表
        
        Returns:
            向量列表
        """
        if self.embedding_model:
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            # 如果没有嵌入模型，让 ChromaDB 使用默认嵌入
            return None
    
    def build_index(self, qa_pairs: List[Dict]):
        """
        构建向量索引
        
        Args:
            qa_pairs: 问答对列表
        """
        print(f"\n[构建索引] 共 {len(qa_pairs)} 个问答对")
        
        # 准备数据
        ids = []
        documents = []
        metadatas = []
        
        for qa in qa_pairs:
            # 文档内容：问题 + 答案
            doc_text = f"问题: {qa['question']['text']}\n\n答案: {qa['answer']['text']}"
            
            ids.append(qa['id'])
            documents.append(doc_text)
            metadatas.append({
                'subject': qa['subject'],
                'category': qa['category'],
                'question_sender': qa['question']['sender'],
                'answer_responder': qa['answer']['responder'],
                'question_time': qa['question']['time'],
                'answer_time': qa['answer']['time']
            })
        
        # 添加到向量数据库
        print("[处理] 生成向量并存储...")
        
        # 分批处理（ChromaDB 每次最多处理 41666 个文档）
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_docs = documents[i:i+batch_size]
            batch_metas = metadatas[i:i+batch_size]
            
            # 生成嵌入向量
            embeddings = self.embed_texts(batch_docs) if self.embedding_model else None
            
            if embeddings:
                self.collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=embeddings,
                    metadatas=batch_metas
                )
            else:
                self.collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_metas
                )
            
            print(f"  处理进度: {min(i+batch_size, len(documents))}/{len(documents)}")
        
        print(f"[完成] 索引构建完成，共 {len(ids)} 条记录")
    
    def search(self, query: str, n_results: int = 5, category_filter: Optional[str] = None) -> Dict:
        """
        语义搜索
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            category_filter: 分类过滤（可选）
        
        Returns:
            搜索结果
        """
        print(f"\n[搜索] 查询: {query}")
        
        # 构建过滤条件
        where_filter = None
        if category_filter:
            where_filter = {"category": category_filter}
        
        # 生成查询向量
        query_embedding = self.embed_texts([query])[0] if self.embedding_model else None
        
        # 执行搜索
        if query_embedding:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter
            )
        else:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
        
        # 格式化结果
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None
            })
        
        print(f"[结果] 找到 {len(formatted_results)} 个匹配项")
        return {
            'query': query,
            'total': len(formatted_results),
            'results': formatted_results
        }
    
    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        count = self.collection.count()
        return {
            'total_qa_pairs': count,
            'collection_name': self.collection.name,
            'persist_directory': str(self.persist_directory)
        }


def demo():
    """演示向量检索"""
    
    print("=" * 80)
    print("AllegroSupport 向量检索系统演示")
    print("=" * 80)
    
    # 初始化知识库
    kb = VectorKnowledgeBase()
    
    # 加载问答对
    qa_pairs = kb.load_qa_pairs()
    
    # 构建索引
    kb.build_index(qa_pairs)
    
    # 获取统计信息
    stats = kb.get_stats()
    print(f"\n[统计] {stats}")
    
    # 演示搜索
    print("\n" + "=" * 80)
    print("语义搜索演示")
    print("=" * 80)
    
    test_queries = [
        "如何修改订舱信息",
        "提单数据错误怎么办",
        "系统提示权限不足",
        "报关单据问题",
    ]
    
    for query in test_queries:
        results = kb.search(query, n_results=2)
        
        print(f"\n【查询】{query}")
        for i, result in enumerate(results['results'], 1):
            print(f"\n  [{i}] 相似度: {1 - result['distance']:.2%}" if result['distance'] else f"\n  [{i}]")
            print(f"  分类: {result['metadata']['category']}")
            print(f"  主题: {result['metadata']['subject']}")
            print(f"  内容: {result['document'][:150]}...")
        
        print("-" * 80)
    
    print("\n[完成] 演示结束")


if __name__ == "__main__":
    demo()
