# -*- coding: utf-8 -*-
"""
海洋AI进展汇总网站 - 数据抓取脚本
抓取 ocean-data-daily-report 和 supplement 两个站点的内容
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os
from urllib.parse import urljoin

# 源站URL
MAIN_URL = "https://tianyunsu.github.io/ocean-data-daily-report/"
SUPPLEMENT_URL = "https://tianyunsu.github.io/ocean-data-daily-report/supplement/"

# 分类关键词配置
CATEGORY_KEYWORDS = {
    "marine-ai": [
        "AI", "ML", "machine learning", "deep learning", "neural network",
        "LLM", "大模型", "人工智能", "神经网络", "GPT", "diffusion",
        "DDPM", "transformer", "GNN", "graph neural", "artificial intelligence",
        "深度学习", "机器学习", "OceanAI", "OceanSTGNN", "GOFLOW", "SeaCast",
        "OceanBench", "Ai2", "ACE2", "AIFS", "DiffSRDA", "DiffUCA"
    ],
    "digital-twin": [
        "digital twin", "DTO", "EDITO", "DITTO", "数字孪生", "digital-twin",
        "digital ocean", "digital replica"
    ],
    "visualization": [
        "visualization", "visualise", "dashboard", "webGL", "D3.js",
        "可视化", "visualization", "plot", "chart", "map", "可视化工具"
    ],
    "data-quality": [
        "quality control", "QA/QC", "validation", "accuracy", "precision",
        "quality", "数据质量", "质量控制", "validation", "评估", "误差"
    ],
    "data-processing": [
        "processing", "xarray", "interpolation", "reconstruction", "reanalysis",
        "数据处理", "处理", "interpolate", "reconstruct", "重建", "融合",
        "super-resolution", "超分辨率", "降尺度", "downscaling"
    ],
    "data-management": [
        "data management", "sharing", "FAIR", "open access", "data policy",
        "数据管理", "共享", "开放获取", "数据治理", "metadata", "元数据"
    ],
    "open-cruise": [
        "cruise", "expedition", "ship time", "SOI", "Schmidt Ocean",
        "航次", "开放航次", "共享船时", "观测航次", "科考船", "科学考察"
    ],
    "data-center": [
        "data center", "repository", "archive", "noda", "database",
        "数据中心", "数据库", "存储", "archive", "Argo", "CMEMS", "GEBCO"
    ],
    "tools-resources": [
        "tool", "code", "library", "GitHub", "software", "package",
        "工具", "代码库", "软件包", "开源", "open source", "PMP", "xarray",
        "python package"
    ]
}

def classify_article(title, summary, tags):
    """根据标题/摘要/标签判断文章分类"""
    text = (title + " " + summary + " " + " ".join(tags)).lower()
    matched_categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                matched_categories.append(category)
                break

    # 默认归类到海洋人工智能（最大类）
    if not matched_categories:
        matched_categories = ["marine-ai"]

    return list(set(matched_categories))

def fetch_page(url):
    """获取页面HTML"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_daily_report(html, source_url, source_type):
    """解析每日日报页面"""
    soup = BeautifulSoup(html, 'html.parser')
    articles = []

    # 提取日期（从URL或页面标题）
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', source_url)
    if date_match:
        date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # 提取标题
    title = soup.find('h1')
    if title:
        title = title.get_text(strip=True)
    else:
        title = "无标题"

    # 提取文章内容块（根据日报结构）
    content_div = soup.find('div', class_='content') or soup.find('article') or soup.find('main')

    if content_div:
        # 查找各个条目（通常是列表项或段落）
        items = content_div.find_all(['li', 'p', 'div'], class_=re.compile(r'item|entry|post'))
        if not items:
            items = content_div.find_all(['li', 'div'], recursive=False)

        for idx, item in enumerate(items):
            item_title = item.get_text(strip=True)
            if len(item_title) > 10:  # 过滤短文本
                # 尝试提取链接
                link = item.find('a')
                item_url = link['href'] if link else source_url
                if not item_url.startswith('http'):
                    item_url = urljoin(source_url, item_url)

                # 提取标签
                item_tags = []
                tag_elements = item.find_all(['span', 'a'], class_=re.compile(r'tag|label'))
                for tag in tag_elements:
                    item_tags.append(tag.get_text(strip=True))

                # 分类
                categories = classify_article(item_title, item.get_text(), item_tags)

                articles.append({
                    "id": f"{date}-{idx:03d}",
                    "date": date,
                    "title": item_title[:200],  # 截断过长标题
                    "summary": item.get_text()[:500],  # 摘要
                    "url": item_url,
                    "source": source_type,
                    "categories": categories,
                    "tags": item_tags,
                    "fetchedAt": datetime.now().isoformat()
                })

    # 如果没有解析到条目，记录整体内容
    if not articles:
        articles.append({
            "id": f"{date}-001",
            "date": date,
            "title": title,
            "summary": soup.get_text()[:500],
            "url": source_url,
            "source": source_type,
            "categories": classify_article(title, soup.get_text(), []),
            "tags": [],
            "fetchedAt": datetime.now().isoformat()
        })

    return articles

def get_archive_links(html, base_url):
    """从归档页面获取所有日报链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    # 查找所有指向posts的链接
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'posts/' in href or href.endswith('.html'):
            full_url = urljoin(base_url, href)
            if full_url not in links:
                links.append(full_url)

    return links

def main():
    """主函数"""
    print("=" * 50)
    print("海洋AI进展汇总网站 - 数据抓取")
    print("=" * 50)

    all_articles = []
    seen_urls = set()

    # 抓取主站
    print(f"\n[1/2] 正在抓取主站: {MAIN_URL}")
    main_html = fetch_page(MAIN_URL)
    if main_html:
        # 获取所有日报链接
        archive_links = get_archive_links(main_html, MAIN_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")

        # 抓取最新10篇（避免超时）
        for i, url in enumerate(archive_links[:10]):
            if url not in seen_urls:
                print(f"   抓取中 ({i+1}/{min(10, len(archive_links))}): {url}")
                html = fetch_page(url)
                if html:
                    articles = parse_daily_report(html, url, "main")
                    for art in articles:
                        if art['url'] not in seen_urls:
                            all_articles.append(art)
                            seen_urls.add(art['url'])
                else:
                    print(f"   跳过: {url}")

    # 抓取补充站
    print(f"\n[2/2] 正在抓取补充站: {SUPPLEMENT_URL}")
    supp_html = fetch_page(SUPPLEMENT_URL)
    if supp_html:
        archive_links = get_archive_links(supp_html, SUPPLEMENT_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")

        for i, url in enumerate(archive_links[:10]):
            if url not in seen_urls:
                print(f"   抓取中 ({i+1}/{min(10, len(archive_links))}): {url}")
                html = fetch_page(url)
                if html:
                    articles = parse_daily_report(html, url, "supplement")
                    for art in articles:
                        if art['url'] not in seen_urls:
                            all_articles.append(art)
                            seen_urls.add(art['url'])

    # 按日期排序（最新在前）
    all_articles.sort(key=lambda x: x['date'], reverse=True)

    # 统计
    print("\n" + "=" * 50)
    print("抓取完成！")
    print(f"共获取 {len(all_articles)} 条进展")

    # 按分类统计
    category_stats = {}
    for art in all_articles:
        for cat in art['categories']:
            category_stats[cat] = category_stats.get(cat, 0) + 1

    print("\n分类统计:")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}条")

    # 生成JSON数据
    output_data = {
        "articles": all_articles,
        "lastUpdated": datetime.now().isoformat(),
        "stats": {
            "total": len(all_articles),
            "byCategory": category_stats
        }
    }

    # 保存数据
    output_path = os.path.join(os.path.dirname(__file__), '..', '_data', 'articles.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存至: {output_path}")
    return output_data

if __name__ == "__main__":
    main()
