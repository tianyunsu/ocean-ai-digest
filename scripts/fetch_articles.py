# -*- coding: utf-8 -*-
"""
海洋AI进展汇总网站 - 数据抓取脚本 v4
使用 BeautifulSoup 正确解析 HTML 结构
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
    "marine-ai": ["AI", "ML", "deep learning", "neural", "arXiv", "Copernicus", "论文", "研究", "模型"],
    "digital-twin": ["digital twin", "DTO", "EDITO", "DITTO", "数字孪生", "Digital Twin"],
    "visualization": ["visualization", "可视化", "dashboard", "可视化工具"],
    "data-quality": ["quality", "QC", "validation", "质量控制", "QA/QC"],
    "data-processing": ["processing", "xarray", "reanalysis", "数据处理", "interpolation"],
    "data-management": ["data management", "FAIR", "open access", "数据管理", "metadata"],
    "open-cruise": ["cruise", "expedition", "Schmidt", "航次", "开放航次", "科考船"],
    "data-center": ["data center", "repository", "archive", "Argo", "GEBCO", "PANGAEA", "CMEMS"],
    "tools-resources": ["tool", "code", "GitHub", "software", "工具", "开源", "library"]
}

def extract_date(text):
    """从文本中提取日期"""
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None

def classify_article(text):
    """根据关键词分类"""
    text_lower = text.lower()
    categories = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                categories.append(cat)
                break
    return categories if categories else ["marine-ai"]

def fetch_page(url):
    """获取页面HTML"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_daily_report(html, source_url, source_type):
    """解析每日日报页面 - 使用 BeautifulSoup"""
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    # 获取报告日期
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', source_url)
    report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else datetime.now().strftime("%Y-%m-%d")
    
    # 找到所有 section
    sections = soup.find_all('section', class_='section')
    
    for section in sections:
        # 获取当前分类
        section_header = section.find('div', class_='section-header')
        section_title_elem = section_header.find('div', class_='section-title') if section_header else None
        section_title = section_title_elem.get_text(strip=True) if section_title_elem else ""
        
        # 映射分类
        category = "marine-ai"
        if "数字孪生" in section_title or "Digital Twin" in section_title:
            category = "digital-twin"
        elif "可视化" in section_title:
            category = "visualization"
        elif "数据质量" in section_title or "QA" in section_title:
            category = "data-quality"
        elif "数据处理" in section_title:
            category = "data-processing"
        elif "管理" in section_title or "共享" in section_title:
            category = "data-management"
        elif "航次" in section_title or "船时" in section_title:
            category = "open-cruise"
        elif "数据中心" in section_title:
            category = "data-center"
        elif "工具" in section_title or "代码" in section_title:
            category = "tools-resources"
        
        # 找到所有 item-card
        item_cards = section.find_all('div', class_='item-card')
        
        for card in item_cards:
            # 提取标题和链接
            title_link = card.find('div', class_='item-title')
            if not title_link:
                continue
            
            link_tag = title_link.find('a')
            if not link_tag:
                continue
            
            article_url = link_tag.get('href', '').strip()
            if not article_url or article_url.startswith('#') or 'tianyunsu.github.io/ocean-data-daily-report' in article_url:
                # 如果是相对链接或者指向日报本身的链接，跳过
                if article_url.startswith('/') or 'tianyunsu' in article_url:
                    continue
            
            # 提取标题
            full_title = link_tag.get_text(strip=True)
            
            # 解析标题格式：序号. 来源（日期）：标题
            title_match = re.match(r'^\d+\.\s*(.+?)（(\d{4}-\d{2}-\d{2})）：(.+)', full_title)
            if title_match:
                source = title_match.group(1).strip()
                article_date = title_match.group(2)
                title = title_match.group(3).strip()
            else:
                source = ""
                article_date = extract_date(full_title) or report_date
                title = re.sub(r'^\d+\.\s*', '', full_title)
                title = re.sub(r'（[^）]*\d{4}-\d{2}-\d{2}[^）]*）', '', title)
                title = title.strip()
            
            # 跳过太短的标题
            if len(title) < 15:
                continue
            
            # 提取摘要
            abstract_elem = card.find('div', class_='item-abstract')
            summary = abstract_elem.get_text(strip=True) if abstract_elem else ""
            
            # 提取元数据日期（如果标题中没有）
            if not article_date or article_date == report_date:
                meta_date = card.find('span', class_='meta-date')
                if meta_date:
                    date_from_meta = extract_date(meta_date.get_text())
                    if date_from_meta:
                        article_date = date_from_meta
            
            # 根据内容关键词添加额外分类
            content = title + " " + summary
            extra_cats = classify_article(content)
            all_cats = list(set([category] + extra_cats))
            
            # 生成ID
            entry_num = len([a for a in articles]) + 1
            article_id = f"{report_date}-{entry_num:03d}"
            
            articles.append({
                "id": article_id,
                "date": article_date,
                "reportDate": report_date,
                "title": title[:200],
                "summary": summary[:500],
                "url": article_url,
                "source": source_type,
                "sourceName": source,
                "categories": all_cats,
                "tags": [],
                "fetchedAt": datetime.now().isoformat()
            })
    
    return articles

def get_archive_links(html, base_url):
    """从归档页面获取所有日报链接"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'posts/' in href and href.endswith('.html'):
            full_url = urljoin(base_url, href)
            if full_url not in links:
                links.append(full_url)

    return links

def main():
    """主函数"""
    print("=" * 60)
    print("海洋AI进展汇总网站 - 数据抓取 v4")
    print("=" * 60)
    
    all_articles = []
    seen_urls = set()
    
    # 抓取主站
    print(f"\n[1/2] 正在抓取主站: {MAIN_URL}")
    main_html = fetch_page(MAIN_URL)
    if main_html:
        archive_links = get_archive_links(main_html, MAIN_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")
        
        for i, url in enumerate(archive_links[:10]):
            print(f"   抓取中 ({i+1}/{min(10, len(archive_links))}): {url}")
            html = fetch_page(url)
            if html:
                articles = parse_daily_report(html, url, "main")
                for art in articles:
                    if art['url'] not in seen_urls and len(art['title']) > 15:
                        all_articles.append(art)
                        seen_urls.add(art['url'])
    
    # 抓取补充站
    print(f"\n[2/2] 正在抓取补充站: {SUPPLEMENT_URL}")
    supp_html = fetch_page(SUPPLEMENT_URL)
    if supp_html:
        archive_links = get_archive_links(supp_html, SUPPLEMENT_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")
        
        for i, url in enumerate(archive_links[:10]):
            print(f"   抓取中 ({i+1}/{min(10, len(archive_links))}): {url}")
            html = fetch_page(url)
            if html:
                articles = parse_daily_report(html, url, "supplement")
                for art in articles:
                    if art['url'] not in seen_urls and len(art['title']) > 15:
                        all_articles.append(art)
                        seen_urls.add(art['url'])
    
    # 按文章日期排序
    all_articles.sort(key=lambda x: x['date'], reverse=True)
    
    # 统计
    print("\n" + "=" * 60)
    print("抓取完成！")
    print(f"共获取 {len(all_articles)} 条进展")
    
    category_stats = {}
    for art in all_articles:
        for cat in art['categories']:
            category_stats[cat] = category_stats.get(cat, 0) + 1
    
    print("\n分类统计:")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count}条")
    
    # 保存数据
    output_data = {
        "articles": all_articles,
        "lastUpdated": datetime.now().isoformat(),
        "stats": {
            "total": len(all_articles),
            "byCategory": category_stats
        }
    }
    
    output_path = os.path.join(os.path.dirname(__file__), '..', '_data', 'articles.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n数据已保存至: {output_path}")
    
    # 示例
    if all_articles:
        print("\n示例数据（前3条）:")
        for art in all_articles[:3]:
            print(f"\n  [{art['date']}] {art['title'][:60]}...")
            print(f"    链接: {art['url'][:80]}...")
    
    return output_data

if __name__ == "__main__":
    main()
