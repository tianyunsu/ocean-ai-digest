# -*- coding: utf-8 -*-
"""
海洋AI进展汇总网站 - 增量抓取脚本 v6

增量更新策略：
- 只抓取最近 7 天的日报
- 与现有 articles.json 合并
- 自动去重
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import os
from urllib.parse import urljoin, urlparse

# 源站URL
MAIN_URL = "https://tianyunsu.github.io/ocean-data-daily-report/"
SUPPLEMENT_URL = "https://tianyunsu.github.io/ocean-data-daily-report/supplement/"

# 抓取最近 N 天的日报
DAYS_TO_FETCH = 7

# 首页/综合页面关键词
HOME_PAGE_KEYWORDS = [
    'home', 'index', '首页', '主页', '最新', 'recent', 'archive', 'archives',
    'blog', 'news', '资讯', '动态', '全部', 'all', 'category', '分类', 'tag',
    '标签', '搜索', 'search', '404', 'not found', 'error', '403', 'forbidden',
    'login', 'sign in', '登录', 'register', '注册', 'about', '关于我们',
    'contact', '联系我', '更多', 'more'
]

# 跳过验证的域名
SKIP_VALIDATION_DOMAINS = [
    'arxiv.org', 'github.com', 'pypi.org', 'conda-forge.org',
    'youtube.com', 'bilibili.com', 'twitter.com', 'x.com'
]

def extract_date(text):
    """从文本中提取日期"""
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None

def get_archive_links_with_date(html, base_url):
    """从归档页面获取所有日报链接（带日期过滤）"""
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'posts/' in href and href.endswith('.html'):
            # 从 URL 中提取日期
            date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', href)
            if date_match:
                full_url = urljoin(base_url, href)
                date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                links.append({
                    'url': full_url,
                    'date': date_str
                })

    return links

def validate_article_url(url, article_title, source):
    """验证文章链接有效性"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()

    for skip_domain in SKIP_VALIDATION_DOMAINS:
        if skip_domain in domain:
            return True, "跳过验证（已知可靠域名）"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        if response.status_code >= 400:
            return False, f"页面失效 (HTTP {response.status_code})"

        soup = BeautifulSoup(response.text, 'html.parser')
        page_title = ""
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text(strip=True).lower()

        if page_title:
            for keyword in HOME_PAGE_KEYWORDS:
                if keyword.lower() in page_title and len(page_title) < 50:
                    return False, f"判定为首页/综合页面"

        return True, "验证通过"

    except requests.exceptions.Timeout:
        return False, "请求超时"
    except requests.exceptions.ConnectionError:
        return False, "连接失败"
    except Exception as e:
        return False, f"验证错误"

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
    """解析每日日报页面"""
    soup = BeautifulSoup(html, 'html.parser')
    articles = []

    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', source_url)
    report_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else datetime.now().strftime("%Y-%m-%d")

    sections = soup.find_all('section', class_='section')

    for section in sections:
        section_header = section.find('div', class_='section-header')
        section_title_elem = section_header.find('div', class_='section-title') if section_header else None
        section_title = section_title_elem.get_text(strip=True) if section_title_elem else ""

        category = "marine-ai"
        if "数字孪生" in section_title or "Digital Twin" in section_title:
            category = "digital-twin"
        elif "可视化" in section_title:
            category = "visualization"
        elif "数据质量" in section_title or "QA" in section_title:
            category = "data-quality"
        elif "数据处理" in section_title:
            category = "data-processing"
        elif "航次" in section_title or "船时" in section_title:
            category = "open-cruise"
        elif "数据中心" in section_title:
            category = "data-center"
        elif "管理" in section_title or "共享" in section_title:
            category = "data-management"
        elif "工具" in section_title or "代码" in section_title:
            category = "tools-resources"

        item_cards = section.find_all('div', class_='item-card')

        for card in item_cards:
            title_link = card.find('div', class_='item-title')
            if not title_link:
                continue

            link_tag = title_link.find('a')
            if not link_tag:
                continue

            article_url = link_tag.get('href', '').strip()
            if not article_url or article_url.startswith('#'):
                continue
            if 'tianyunsu.github.io/ocean-data-daily-report' in article_url:
                continue

            full_title = link_tag.get_text(strip=True)

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

            if len(title) < 15:
                continue

            # 跳过已有链接
            if article_url in existing_urls:
                continue

            # 验证链接
            is_valid, _ = validate_article_url(article_url, title, source_type)
            if not is_valid:
                continue

            abstract_elem = card.find('div', class_='item-abstract')
            summary = abstract_elem.get_text(strip=True) if abstract_elem else ""

            if not article_date or article_date == report_date:
                meta_date = card.find('span', class_='meta-date')
                if meta_date:
                    date_from_meta = extract_date(meta_date.get_text())
                    if date_from_meta:
                        article_date = date_from_meta

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
                "categories": [category],
                "tags": [],
                "fetchedAt": datetime.now().isoformat()
            })

    return articles

def main():
    """主函数"""
    print("=" * 60)
    print("海洋AI进展汇总 - 增量抓取 v6")
    print(f"策略: 只抓取最近 {DAYS_TO_FETCH} 天的日报")
    print("=" * 60)

    # 读取现有数据
    data_file = os.path.join(os.path.dirname(__file__), '..', '_data', 'articles.json')
    existing_articles = []
    global existing_urls
    existing_urls = set()

    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing_articles = data.get('articles', [])
            existing_urls = {art['url'] for art in existing_articles}
            print(f"\n[现有数据] 共 {len(existing_articles)} 条记录")

    # 计算日期范围
    today = datetime.now()
    cutoff_date = (today - timedelta(days=DAYS_TO_FETCH)).strftime('%Y-%m-%d')
    print(f"[日期范围] {cutoff_date} 至今\n")

    all_new_articles = []
    total_validated = 0

    # 抓取主站
    print(f"[1/2] 正在抓取主站: {MAIN_URL}")
    main_html = fetch_page(MAIN_URL)
    if main_html:
        archive_links = get_archive_links_with_date(main_html, MAIN_URL)
        # 过滤日期
        recent_links = [l for l in archive_links if l['date'] >= cutoff_date]
        print(f"   找到 {len(archive_links)} 个日报，其中最近 {DAYS_TO_FETCH} 天有 {len(recent_links)} 个")

        for i, link_info in enumerate(recent_links):
            html = fetch_page(link_info['url'])
            if html:
                articles = parse_daily_report(html, link_info['url'], "main")
                for art in articles:
                    total_validated += 1
                    all_new_articles.append(art)
            if (i + 1) % 3 == 0 or (i + 1) == len(recent_links):
                print(f"   进度: {i+1}/{len(recent_links)} | 新增: {len(all_new_articles)} 条")

    # 抓取补充站
    print(f"\n[2/2] 正在抓取补充站: {SUPPLEMENT_URL}")
    supp_html = fetch_page(SUPPLEMENT_URL)
    if supp_html:
        archive_links = get_archive_links_with_date(supp_html, SUPPLEMENT_URL)
        recent_links = [l for l in archive_links if l['date'] >= cutoff_date]
        print(f"   找到 {len(archive_links)} 个日报，其中最近 {DAYS_TO_FETCH} 天有 {len(recent_links)} 个")

        for i, link_info in enumerate(recent_links):
            html = fetch_page(link_info['url'])
            if html:
                articles = parse_daily_report(html, link_info['url'], "supplement")
                for art in articles:
                    total_validated += 1
                    all_new_articles.append(art)
            if (i + 1) % 3 == 0 or (i + 1) == len(recent_links):
                print(f"   进度: {i+1}/{len(recent_links)} | 新增: {len(all_new_articles)} 条")

    # 合并数据
    all_articles = all_new_articles + existing_articles
    all_articles.sort(key=lambda x: x['date'], reverse=True)

    # 重新编号
    for i, art in enumerate(all_articles):
        art['id'] = f"{art['date']}-{i+1:03d}"

    # 统计
    new_count = len(all_new_articles)
    total_count = len(all_articles)

    print("\n" + "=" * 60)
    if new_count > 0:
        print(f"✅ 增量抓取完成！")
        print(f"   新增: {new_count} 条")
        print(f"   总计: {total_count} 条")
    else:
        print("📭 今日无新增进展")
        print(f"   现有: {total_count} 条")

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
            "total": total_count,
            "newToday": new_count,
            "byCategory": category_stats
        }
    }

    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存至: {data_file}")

    # 新增示例
    if all_new_articles:
        print("\n新增进展（前3条）:")
        for art in all_new_articles[:3]:
            print(f"\n  [{art['date']}] {art['title'][:60]}...")
            print(f"    链接: {art['url'][:80]}...")

    return output_data

if __name__ == "__main__":
    main()
