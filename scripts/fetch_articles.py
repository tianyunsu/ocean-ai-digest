# -*- coding: utf-8 -*-
"""
海洋AI进展汇总网站 - 数据抓取脚本 v5
新增链接有效性验证功能：
- 页面是否失效
- 页面内容是否与链接标题相符
- 页面是否为首页或综合页面
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import os
from urllib.parse import urljoin, urlparse

# 源站URL
MAIN_URL = "https://tianyunsu.github.io/ocean-data-daily-report/"
SUPPLEMENT_URL = "https://tianyunsu.github.io/ocean-data-daily-report/supplement/"

# 首页/综合页面关键词（这些页面会被判定为非具体文章页）
HOME_PAGE_KEYWORDS = [
    'home', 'index', '首页', '主页', '最新', 'recent', 'archive', 'archives',
    'blog', 'news', '资讯', '动态', '全部', 'all', 'category', '分类', 'tag',
    '标签', '搜索', 'search', '404', 'not found', 'error', '403', 'forbidden',
    'login', 'sign in', '登录', 'register', '注册', 'about', '关于我们',
    'contact', '联系我', '更多', 'more'
]

# 跳过验证的域名（这些域名通常会重定向到首页或有特殊页面结构）
SKIP_VALIDATION_DOMAINS = [
    'arxiv.org', 'github.com', 'pypi.org', 'conda-forge.org',
    'youtube.com', 'bilibili.com', 'twitter.com', 'x.com'
]

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

def validate_article_url(url, article_title, source):
    """
    验证文章链接的有效性
    
    返回值:
        (is_valid, reason): 
            - is_valid: True 表示有效，False 表示无效
            - reason: 原因说明（用于日志）
    """
    # 检查域名是否跳过验证
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    for skip_domain in SKIP_VALIDATION_DOMAINS:
        if skip_domain in domain:
            return True, "跳过验证（已知可靠域名）"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # 检查HTTP状态码
        if response.status_code >= 400:
            return False, f"页面失效 (HTTP {response.status_code})"
        
        if response.status_code >= 300:
            # 重定向但最终成功
            final_url = response.url
            if final_url != url and any(hp in final_url.lower() for hp in HOME_PAGE_KEYWORDS):
                return False, f"重定向至综合页面: {final_url[:80]}"
        
        # 解析页面内容
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
        except:
            return False, "页面解析失败"
        
        # 获取页面标题
        page_title = ""
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text(strip=True).lower()
        
        # 检查是否为首页或综合页面
        if page_title:
            # 检查标题是否包含首页关键词
            for keyword in HOME_PAGE_KEYWORDS:
                if keyword.lower() in page_title:
                    # 排除标题本身包含该关键词但实际是文章的情况
                    # 如果标题很短且只有首页关键词，可能是首页
                    if len(page_title) < 50:
                        return False, f"判定为首页/综合页面 (标题: {page_title[:50]})"
        
        # 检查标题是否与文章标题相关
        if article_title and page_title:
            # 提取文章标题的关键词语（去掉常见前缀后缀）
            title_keywords = article_title.lower()
            title_keywords = re.sub(r'[\[\]()【】（）""''""《》<>]', ' ', title_keywords)
            title_keywords = re.sub(r'\s+', ' ', title_keywords).strip()
            
            # 取标题的前20个字符作为关键词
            key_phrase = title_keywords[:20] if len(title_keywords) >= 20 else title_keywords
            
            # 检查页面标题是否包含文章标题的关键词
            if len(key_phrase) >= 10:  # 只检查足够长的关键词
                # 移除常见英文冠词和介词
                stop_words = ['the', 'a', 'an', 'of', 'in', 'on', 'at', 'for', 'to', 'and', 'or', 'with', 'by']
                words = [w for w in key_phrase.split() if w not in stop_words and len(w) >= 3]
                
                if words:
                    matched = False
                    for word in words[:3]:  # 检查前3个有意义的词
                        if word in page_title:
                            matched = True
                            break
                    
                    if not matched:
                        return False, f"标题不符 (页面: {page_title[:50]}... vs 文章: {article_title[:30]}...)"
        
        return True, "验证通过"
        
    except requests.exceptions.Timeout:
        return False, "请求超时"
    except requests.exceptions.ConnectionError:
        return False, "连接失败"
    except Exception as e:
        return False, f"验证错误: {str(e)[:30]}"

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
        
        # 映射分类（注意顺序：更具体的匹配放前面）
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
            
            # 【新增】验证文章链接有效性
            # 验证结果：(is_valid, reason)
            is_valid, validation_reason = validate_article_url(article_url, title, source_type)
            if not is_valid:
                # 验证失败，跳过该文章
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
            
            # 只使用日报所在的分类，不再根据关键词添加额外分类
            all_cats = [category]
            
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
    print("海洋AI进展汇总网站 - 数据抓取 v5")
    print("新增功能: 链接有效性验证")
    print("=" * 60)
    
    all_articles = []
    seen_urls = set()
    
    # 统计变量
    total_extracted = 0  # 提取的文章总数
    total_validated = 0  # 通过验证的文章数
    
    # 抓取主站
    print(f"\n[1/2] 正在抓取主站: {MAIN_URL}")
    main_html = fetch_page(MAIN_URL)
    if main_html:
        archive_links = get_archive_links(main_html, MAIN_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")
        print(f"   正在验证每篇文章链接有效性...")
        
        for i, url in enumerate(archive_links):
            html = fetch_page(url)
            if html:
                articles = parse_daily_report(html, url, "main")
                for art in articles:
                    total_extracted += 1
                    if art['url'] not in seen_urls and len(art['title']) > 15:
                        all_articles.append(art)
                        seen_urls.add(art['url'])
                        total_validated += 1
            # 显示进度
            if (i + 1) % 5 == 0 or (i + 1) == len(archive_links):
                print(f"   进度: {i+1}/{len(archive_links)} | 已验证: {total_validated} 条")
    
    # 抓取补充站
    print(f"\n[2/2] 正在抓取补充站: {SUPPLEMENT_URL}")
    supp_html = fetch_page(SUPPLEMENT_URL)
    if supp_html:
        archive_links = get_archive_links(supp_html, SUPPLEMENT_URL)
        print(f"   找到 {len(archive_links)} 个日报页面")
        print(f"   正在验证每篇文章链接有效性...")
        
        for i, url in enumerate(archive_links):
            html = fetch_page(url)
            if html:
                articles = parse_daily_report(html, url, "supplement")
                for art in articles:
                    total_extracted += 1
                    if art['url'] not in seen_urls and len(art['title']) > 15:
                        all_articles.append(art)
                        seen_urls.add(art['url'])
                        total_validated += 1
            # 显示进度
            if (i + 1) % 5 == 0 or (i + 1) == len(archive_links):
                print(f"   进度: {i+1}/{len(archive_links)} | 已验证: {total_validated} 条")
    
    # 按文章日期排序
    all_articles.sort(key=lambda x: x['date'], reverse=True)
    
    # 统计
    print("\n" + "=" * 60)
    print("抓取完成！")
    print(f"✓ 通过验证: {len(all_articles)} 条进展")
    print(f"  (链接有效性验证: 无效链接已被过滤)")
    
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
