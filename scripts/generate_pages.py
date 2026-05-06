# -*- coding: utf-8 -*-
"""
生成各分类HTML页面的脚本
"""

import json
import os
from datetime import datetime

CATEGORY_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{category_name} | 海洋AI进展汇总</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: {category_color};
            --bg: #F8FAFC;
            --card-bg: #FFFFFF;
            --text: #1E293B;
            --text-secondary: #64748B;
            --border: #E2E8F0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        header {{
            background: linear-gradient(135deg, {category_color} 0%, {category_color_light} 100%);
            color: white;
            padding: 48px 0;
        }}

        header .container {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}

        .header-icon {{
            font-size: 3rem;
        }}

        header h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .header-subtitle {{
            opacity: 0.9;
        }}

        nav {{
            background: white;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        nav .container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 64px;
        }}

        .nav-links {{
            display: flex;
            gap: 32px;
        }}

        .nav-links a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.95rem;
            transition: color 0.2s;
        }}

        .nav-links a:hover,
        .nav-links a.active {{
            color: var(--primary);
        }}

        .stats-bar {{
            background: white;
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
        }}

        .stats-bar .container {{
            display: flex;
            gap: 32px;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .stat-value {{
            font-weight: 600;
            color: var(--primary);
        }}

        .articles-section {{
            padding: 32px 0 80px;
        }}

        .articles-list {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .article-card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 24px;
            border: 1px solid var(--border);
            transition: all 0.2s;
        }}

        .article-card:hover {{
            border-color: var(--primary);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}

        .article-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .article-date {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}

        .article-source {{
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 500;
        }}

        .article-source.main {{
            background: #DBEAFE;
            color: #1E40AF;
        }}

        .article-source.supplement {{
            background: #FEF3C7;
            color: #92400E;
        }}

        .article-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.4;
        }}

        .article-title a {{
            color: inherit;
            text-decoration: none;
        }}

        .article-title a:hover {{
            color: var(--primary);
        }}

        .article-summary {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 12px;
        }}

        .article-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}

        .article-tag {{
            font-size: 0.75rem;
            padding: 2px 8px;
            background: var(--bg);
            border-radius: 4px;
            color: var(--text-secondary);
        }}

        footer {{
            background: var(--text);
            color: white;
            padding: 24px 0;
            text-align: center;
        }}

        footer a {{
            color: #0EA5E9;
            text-decoration: none;
        }}

        @media (max-width: 768px) {{
            .nav-links {{
                display: none;
            }}

            header h1 {{
                font-size: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-icon">{category_icon}</div>
            <div>
                <h1>{category_name}</h1>
                <p class="header-subtitle">{category_description}</p>
            </div>
        </div>
    </header>

    <nav>
        <div class="container">
            <div class="nav-links">
                <a href="../index.html">首页</a>
                <a href="../all.html">全部进展</a>
                <a href="marine-ai.html" class="active">海洋AI</a>
                <a href="digital-twin.html">数字孪生</a>
                <a href="data-processing.html">数据处理</a>
            </div>
        </div>
    </nav>

    <div class="stats-bar">
        <div class="container">
            <div class="stat-item">
                <span class="stat-value">{article_count}</span> 条进展
            </div>
            <div class="stat-item">
                📅 最后更新: {last_updated}
            </div>
        </div>
    </div>

    <main class="articles-section">
        <div class="container">
            <div class="articles-list" id="articlesList">
                {articles_html}
            </div>
        </div>
    </main>

    <footer>
        <div class="container">
            <p>数据来源: <a href="https://tianyunsu.github.io/ocean-data-daily-report/" target="_blank">海洋AI技术日报</a> &
               <a href="https://tianyunsu.github.io/ocean-data-daily-report/supplement/" target="_blank">补充日报</a></p>
        </div>
    </footer>
</body>
</html>
'''

def generate_category_pages():
    """生成所有分类页面"""

    # 读取数据
    with open('_data/articles.json', 'r', encoding='utf-8') as f:
        articles_data = json.load(f)

    with open('_data/categories.json', 'r', encoding='utf-8') as f:
        categories_data = json.load(f)

    articles = articles_data['articles']
    categories = {cat['id']: cat for cat in categories_data['categories']}

    for cat_id, cat_info in categories.items():
        # 筛选该分类的文章
        cat_articles = [a for a in articles if cat_id in a['categories']]
        cat_articles.sort(key=lambda x: x['date'], reverse=True)

        # 生成文章HTML
        articles_html = ''
        for art in cat_articles:
            source_label = '日报' if art['source'] == 'main' else '补充'
            tags_html = ''.join([f'<span class="article-tag">{tag}</span>' for tag in art['tags'][:5]])

            articles_html += f'''
            <article class="article-card">
                <div class="article-header">
                    <span class="article-date">📅 {art['date']}</span>
                    <span class="article-source {art['source']}">{source_label}</span>
                </div>
                <h3 class="article-title">
                    <a href="{art['url']}" target="_blank">{art['title']}</a>
                </h3>
                <p class="article-summary">{art['summary']}</p>
                <div class="article-tags">{tags_html}</div>
            </article>
            '''

        if not articles_html:
            articles_html = '<p style="text-align: center; color: #64748B; padding: 40px;">暂无该分类的进展</p>'

        # 生成页面
        page_html = CATEGORY_TEMPLATE.format(
            category_id=cat_id,
            category_name=cat_info['name'],
            category_icon=cat_info['icon'],
            category_description=cat_info['description'],
            category_color=cat_info['color'],
            category_color_light=cat_info['color'] + '99',
            article_count=len(cat_articles),
            last_updated=datetime.now().strftime('%Y-%m-%d'),
            articles_html=articles_html
        )

        # 保存文件
        output_path = f'_data/../categories/{cat_id}.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(page_html)

        print(f'Generated: {output_path} ({len(cat_articles)} articles)')

    print('\nAll category pages generated successfully!')

if __name__ == '__main__':
    generate_category_pages()
