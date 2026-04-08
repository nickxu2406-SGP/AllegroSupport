# -*- coding: utf-8 -*-
"""
AllegroSupport 知识库 Web 查询界面
基于关键词匹配的轻量级搜索（无需 ChromaDB）
"""

import sys
import io
import json
import re
from pathlib import Path
from typing import Optional, List

# 设置 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============================================================
# 关键词搜索知识库（内嵌实现，无依赖）
# ============================================================

class SimpleKnowledgeBase:
    """轻量级知识库（基于关键词匹配）"""

    STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'dear', 'thanks', 'thank', 'please', 'best', 'regards', 'kind',
        'hi', 'hello', 'kindly', 'could', 'would', 'also', 'our', 'we'
    }

    def __init__(self, json_file: str = None):
        """初始化知识库"""
        if json_file is None:
            json_file = Path(__file__).parent.parent / "data" / "qa_pairs.json"
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.qa_pairs = data['qa_pairs']
        self.categories = data['categories']

    def _extract_keywords(self, text: str) -> set:
        """提取关键词集合（支持中英文）"""
        if not text:
            return set()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.lower().split()
        # 英文停用词过滤
        filtered = {w for w in words if len(w) > 2 and w not in self.STOPWORDS}
        # 中文处理：将连续中文字符串按 2-gram 和 3-gram 切分
        chinese_text = re.findall(r'[\u4e00-\u9fff]+', text)
        for chunk in chinese_text:
            if len(chunk) >= 2:
                for i in range(len(chunk) - 1):
                    n2 = chunk[i:i+2]
                    if len(n2) == 2:
                        filtered.add(n2)
            if len(chunk) >= 3:
                for i in range(len(chunk) - 2):
                    n3 = chunk[i:i+3]
                    filtered.add(n3)
        return filtered

    # 订舱关键词：出现时对订舱操作类问答加权
    BOOKING_BOOST_KEYWORDS = {
        'booking', 'so', 'slot', '订舱', 'vd', 'route', 'pol', 'pod',
        'free time', 'free day', 'cancel', 'amend', 'rfq', 'rate',
        'container', 'vessel', 'voyage', 'commodity', 'weight', 'hazmat',
        'freight', 'agreement', 'bl code', 'blcode', 'cargo'
    }

    def search(self, query: str, n_results: int = 5,
               category_filter: Optional[str] = None,
               booking_priority: bool = False) -> dict:
        """
        搜索问答对

        Args:
            query: 查询文本
            n_results: 返回数量
            category_filter: 分类过滤
            booking_priority: 订舱优先模式，命中订舱关键词时对订舱类加权

        Returns:
            dict with 'results' key containing list of dicts
        """
        query_keywords = self._extract_keywords(query)
        if not query_keywords:
            return {'query': query, 'total': 0, 'results': []}

        # 检测是否为订舱相关查询
        is_booking_query = any(
            kw in ' '.join(query_keywords) for kw in self.BOOKING_BOOST_KEYWORDS
        )

        scored = []
        for qa in self.qa_pairs:
            if category_filter and qa.get('category') != category_filter:
                continue

            qa_text = (f"{qa.get('question', {}).get('text', '')} "
                       f"{qa.get('answer', {}).get('text', '')} "
                       f"{qa.get('category', '')}")
            qa_keywords = self._extract_keywords(qa_text)
            common = query_keywords & qa_keywords

            if common:
                score = len(common) / max(len(query_keywords), 1)

                # 订舱优先加权：查询含订舱关键词 + 当前为订舱类 → 加权 50%
                if is_booking_query and qa.get('category') == '订舱操作':
                    score *= 1.5

                scored.append((qa, score, common))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for qa, score, matched_kw in scored[:n_results]:
            doc_text = f"问题: {qa.get('question', {}).get('text', '')}\n\n答案: {qa.get('answer', {}).get('text', '')}"
            results.append({
                'id': qa.get('id', ''),
                'document': doc_text,
                'metadata': {
                    'subject': qa.get('subject', ''),
                    'category': qa.get('category', ''),
                    'question_sender': qa.get('question', {}).get('sender', ''),
                    'answer_responder': qa.get('answer', {}).get('responder', ''),
                },
                'distance': 1 - score  # 反向相似度
            })

        return {'query': query, 'total': len(results), 'results': results}

    def get_stats(self) -> dict:
        return {
            'total_qa_pairs': len(self.qa_pairs),
            'collection_name': 'allegrosupport_simple',
            'persist_directory': ''
        }


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="AllegroSupport 知识库",
    description="Allegro 系统支持问答检索系统",
    version="1.0.0"
)

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

kb: Optional[SimpleKnowledgeBase] = None


def get_kb() -> SimpleKnowledgeBase:
    global kb
    if kb is None:
        print("[初始化] 加载知识库...")
        script_dir = Path(__file__).parent
        # 优先加载优化后的数据（147条，已审核45条）
        json_file = script_dir.parent / "data_180days_optimized" / "qa_pairs_optimized.json"
        if not json_file.exists():
            # 回退到旧数据
            json_file = script_dir.parent / "data" / "qa_pairs.json"
        kb = SimpleKnowledgeBase(str(json_file))
        print(f"[完成] 知识库加载完成，共 {len(kb.qa_pairs)} 个问答对")
    return kb


class SearchRequest(BaseModel):
    query: str
    n_results: int = 5
    category: Optional[str] = None
    booking_priority: bool = False


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>AllegroSupport 知识库 v1.2</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .search-box {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            margin-bottom: 30px;
        }
        .search-input-group { display: flex; gap: 15px; margin-bottom: 15px; }
        .search-input {
            flex: 1;
            padding: 15px 20px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            transition: border-color 0.3s;
        }
        .search-input:focus { outline: none; border-color: #667eea; }
        .search-btn {
            padding: 15px 40px;
            font-size: 16px;
            font-weight: bold;
            color: white;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .search-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .filters { display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
        .filter-label { font-size: 14px; color: #666; }
        .filter-select {
            padding: 10px 15px;
            font-size: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            cursor: pointer;
        }
        .results {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }
        .result-item {
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .result-item:hover {
            transform: translateX(5px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        .result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .result-category {
            display: inline-block;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: bold;
            color: #667eea;
            background: #e8f0ff;
            border-radius: 20px;
        }
        .result-similarity { font-size: 14px; color: #666; }
        .result-subject { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .result-content { font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 10px; }
        .result-meta { font-size: 12px; color: #999; border-top: 1px solid #e0e0e0; padding-top: 10px; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .no-results { text-align: center; padding: 40px; color: #999; }
        .stats {
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: white;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            flex-wrap: wrap;
            gap: 10px;
        }
        .stat-item { text-align: center; }
        .stat-value { font-size: 36px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 14px; color: #666; margin-top: 5px; }
        .hint { font-size: 12px; color: #999; margin-top: 10px; text-align: center; }
        .examples { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; justify-content: center; }
        .example-btn {
            padding: 6px 14px;
            font-size: 13px;
            color: #667eea;
            background: #e8f0ff;
            border: 1px solid #667eea;
            border-radius: 20px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .example-btn:hover { background: #d0e0ff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AllegroSupport 知识库</h1>
            <p>IT 支持问答检索系统 - 快速找到历史解决方案</p>
        </div>

        <div class="stats" id="stats">
            <div class="stat-item">
                <div class="stat-value" id="total-qa">-</div>
                <div class="stat-label">问答对数量</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="total-categories">-</div>
                <div class="stat-label">问题分类</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="total-supporters">-</div>
                <div class="stat-label">IT 支持人员</div>
            </div>
        </div>

        <div class="search-box">
            <div class="search-input-group">
                <input type="text" class="search-input" id="query"
                       placeholder="输入问题，例如：如何修改订舱信息？"
                       onkeypress="if(event.key==='Enter')search()" />
                <button class="search-btn" onclick="search()">搜索</button>
            </div>
            <div class="filters">
                <span class="filter-label">分类过滤：</span>
                <select class="filter-select" id="category">
                    <option value="">全部</option>
                    <option value="订舱操作">订舱操作</option>
                    <option value="提单操作">提单操作</option>
                    <option value="费用相关">费用相关</option>
                    <option value="报关操作">报关操作</option>
                    <option value="系统问题">系统问题</option>
                    <option value="权限申请">权限申请</option>
                    <option value="其他">其他</option>
                </select>
                <span class="filter-label">返回数量：</span>
                <select class="filter-select" id="nResults">
                    <option value="3">3 条</option>
                    <option value="5" selected>5 条</option>
                    <option value="10">10 条</option>
                </select>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:14px;color:#667eea;font-weight:bold;">
                    <input type="checkbox" id="bookingPriority" style="width:16px;height:16px;cursor:pointer;" />
                    订舱优先
                </label>
            </div>
            <div class="hint">试试这些示例：</div>
            <div class="examples">
                <button class="example-btn" onclick="searchExample('booking SO')">booking SO</button>
                <button class="example-btn" onclick="searchExample('VD move')">VD move</button>
                <button class="example-btn" onclick="searchExample('route update')">route update</button>
                <button class="example-btn" onclick="searchExample('slot booking')">slot booking</button>
                <button class="example-btn" onclick="searchExample('free time')">free time</button>
                <button class="example-btn" onclick="searchExample('提单错误')">提单错误</button>
                <button class="example-btn" onclick="searchExample('报关问题')">报关问题</button>
                <button class="example-btn" onclick="searchExample('BL code')">BL code</button>
            </div>
        </div>

        <div class="results" id="results">
            <div class="no-results">
                <p>输入问题开始搜索</p>
            </div>
        </div>
    </div>

    <script>
        async function loadStats() {
            try {
                const r = await fetch('/api/stats');
                const d = await r.json();
                document.getElementById('total-qa').textContent = d.total_qa_pairs || 0;
                document.getElementById('total-categories').textContent = d.total_categories || 0;
                document.getElementById('total-supporters').textContent = d.total_supporters || 0;
            } catch (e) {
                console.error('统计加载失败', e);
            }
        }

        function searchExample(q) {
            document.getElementById('query').value = q;
            search();
        }

        async function search() {
            const query = document.getElementById('query').value.trim();
            if (!query) { alert('请输入查询内容'); return; }
            const category = document.getElementById('category').value;
            const nResults = document.getElementById('nResults').value;
            const bookingPriority = document.getElementById('bookingPriority').checked;
            document.getElementById('results').innerHTML = '<div class="loading">搜索中...</div>';
            try {
                console.log('发送搜索请求:', query);
                const r = await fetch('/api/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query,
                        n_results: parseInt(nResults),
                        category: category || null,
                        booking_priority: bookingPriority
                    })
                });
                console.log('响应状态:', r.status);
                if (!r.ok) {
                    throw new Error('HTTP ' + r.status + ': ' + r.statusText);
                }
                const d = await r.json();
                console.log('搜索结果:', d);
                renderResults(d);
            } catch (e) {
                console.error('搜索错误:', e);
                document.getElementById('results').innerHTML =
                    '<div class="no-results"><p>搜索失败: ' + e.message + '</p></div>';
            }
        }

        function renderResults(d) {
            const div = document.getElementById('results');
            if (!d.results || d.results.length === 0) {
                div.innerHTML = '<div class="no-results"><p>未找到相关结果</p></div>';
                return;
            }
            let html = '';
            d.results.forEach(item => {
                const sim = item.distance ? (100 - item.distance * 100).toFixed(1) + '%' : '-';
                const content = item.document.length > 300
                    ? item.document.substring(0, 300) + '...'
                    : item.document;
                html += `
                    <div class="result-item">
                        <div class="result-header">
                            <span class="result-category">${item.category}</span>
                            <span class="result-similarity">匹配度: ${sim}</span>
                        </div>
                        <div class="result-subject">${item.subject}</div>
                        <div class="result-content">${content.replace(/\\n/g, '<br>')}</div>
                        <div class="result-meta">
                            提问人: ${item.question_sender} | 回复人: ${item.answer_responder}
                        </div>
                    </div>`;
            });
            div.innerHTML = html;
        }

        loadStats();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=HTML_TEMPLATE, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })


@app.get("/api/stats")
async def get_stats():
    k = get_kb()
    supporters = {qa['answer']['responder'] for qa in k.qa_pairs}
    return {
        'total_qa_pairs': len(k.qa_pairs),
        'total_categories': len(k.categories),
        'total_supporters': len(supporters),
        'categories': k.categories
    }


@app.post("/api/search")
async def search(request: SearchRequest):
    k = get_kb()
    try:
        # 调试：打印查询参数
        print(f"[搜索] query='{request.query}' n_results={request.n_results} category={request.category}")
        query_kw = k._extract_keywords(request.query)
        print(f"[搜索] 查询关键词: {query_kw}")

        results = k.search(
            query=request.query,
            n_results=request.n_results,
            category_filter=request.category,
            booking_priority=request.booking_priority
        )
        print(f"[搜索] 结果数: {results['total']}")
        formatted = []
        for item in results['results']:
            formatted.append({
                'id': item['id'],
                'subject': item['metadata']['subject'],
                'category': item['metadata']['category'],
                'question_sender': item['metadata']['question_sender'],
                'answer_responder': item['metadata']['answer_responder'],
                'document': item['document'],
                'distance': item['distance']
            })
        return {'query': request.query, 'total': len(formatted), 'results': formatted}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("\n============================================")
    print("  AllegroSupport 知识库 Web 服务")
    print("  访问地址: http://localhost:8000")
    print("  API 文档: http://localhost:8000/docs")
    print("============================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
