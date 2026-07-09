# -*- coding: utf-8 -*-
"""
海洋AI进展汇总网站 - 增量抓取脚本 v8

增量更新策略：
- 只抓取最近 7 天的日报
- 与现有 articles.json 合并
- 链接去重（URL 级别）
- 标题去重（title 级别，防止同一条目出现在多个日报）
- 验证每条链接的有效性（HTTP 状态码 + 内容相关性）

修复记录（v8 vs v7）：
- 修复 parse_daily_report() 中 section 选择器错误
  v7: soup.find_all('div', class_='section')  ← 错误，页面用 <section> 不是 <div>
  v8: soup.find_all(class_='section')          ← 兼容 <section> 和 <div>
- 修复 item 选择器错误
  v7: section.find_all('div', class_='item')   ← 错误，页面用 item-card 不是 item
  v8: section.find_all(class_='item-card')     ← 兼容 item-card 和 item
- 原因：日报模板已更新为 <section class="section"> + <div class="item-card">

修复记录（v7 vs v6）：
- 新增标题级去重：跨 reportDate 的相同标题只保留最新一条
- 将 validate_links.py 的验证逻辑集成进增量抓取，确保新增内容有效
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import os
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 源站URL
MAIN_URL = "https://tianyunsu.github.io/ocean-data-daily-report/"
SUPPLEMENT_URL = "https://tianyunsu.github.io/ocean-data-daily-report/supplement/"

# 抓取最近 N 天的日报（设为 14 天以覆盖周末/节假日间隙）
DAYS_TO_FETCH = 14

# 首页/综合页面关键词（用于判断链接是否指向有效文章页）
HOME_PAGE_KEYWORDS = [
    'home', 'index', '首页', '主页', '最新', 'recent', 'archive', 'archives',
    'blog', 'news', '资讯', '动态', '全部', 'all', 'category', '分类', 'tag',
    '标签', '搜索', 'search', '404', 'not found', 'error', '403', 'forbidden',
    'login', 'sign in', '登录', 'register', '注册', 'about', '关于我们',
    'contact', '联系我', '更多', 'more'
]

# 跳过 HTTP 验证的域名（已知可靠，直接信任）
SKIP_VALIDATION_DOMAINS = [
    'arxiv.org', 'github.com', 'pypi.org', 'conda-forge.org',
    'youtube.com', 'bilibili.com', 'twitter.com', 'x.com',
    'nature.com', 'science.org', 'springer.com', 'wiley.com',
    'sciencedirect.com', 'agu.org', 'eos.org',
]

# 全局已存在 URL 集合（在 main() 中初始化）
existing_urls = set()


def extract_date(text):
    """从文本中提取 YYYY-MM-DD 日期"""
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def get_archive_links_with_date(html, base_url):
    """
    从归档首页获取所有日报链接（带日期信息）。
    支持主站（posts/）和补充站（supplement/posts/）两种路径。
    返回列表去重（同一 URL 只保留一次）。
    """
    soup = BeautifulSoup(html, 'html.parser')
    seen_urls = set()
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'posts/' in href and href.endswith('.html'):
            date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', href)
            if date_match:
                full_url = urljoin(base_url, href)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                links.append({
                    'url': full_url,
                    'date': date_str
                })

    return links


def validate_article_url(url, title="", source_type=""):
    """
    验证文章外链的有效性。
    返回: (is_valid: bool, reason: str)

    验证逻辑：
    1. 已知可靠域名 → 跳过验证，直接返回 True
    2. HTTP 状态码 >= 400 → 无效
    3. 页面标题含首页/综合页关键词（且标题较短）→ 判定为非文章页
    4. 其余情况 → 有效
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()

    for skip_domain in SKIP_VALIDATION_DOMAINS:
        if skip_domain in domain:
            return True, "跳过验证（已知可靠域名）"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=12, allow_redirects=True)

        if response.status_code >= 400:
            return False, f"页面失效 (HTTP {response.status_code})"

        # 检查重定向目标是否为综合页面
        if response.url != url:
            final_path = response.url.lower()
            for kw in HOME_PAGE_KEYWORDS:
                if kw in final_path and len(final_path) < 80:
                    return False, f"重定向至综合页面: {response.url[:60]}"

        # 解析页面标题
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
        except Exception:
            return False, "页面解析失败"

        page_title = ""
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text(strip=True).lower()

        # 综合页面判定（标题较短且含关键词）
        if page_title:
            for keyword in HOME_PAGE_KEYWORDS:
                if keyword.lower() in page_title and len(page_title) < 50:
                    return False, f"判定为首页/综合页面 (标题: {page_title[:40]})"

        return True, "验证通过"

    except requests.exceptions.Timeout:
        return False, "请求超时"
    except requests.exceptions.ConnectionError:
        return False, "连接失败"
    except Exception as e:
        return False, f"验证错误: {str(e)[:30]}"


def fetch_page(url):
    """获取页面 HTML，失败返回 None"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"    [WARN] 抓取失败 {url}: {e}")
        return None


def get_category(section_title):
    """根据板块标题推断分类 slug"""
    if "数字孪生" in section_title or "Digital Twin" in section_title:
        return "digital-twin"
    elif "可视化" in section_title:
        return "visualization"
    elif "数据质量" in section_title or "QA" in section_title:
        return "data-quality"
    elif "数据处理" in section_title:
        return "data-processing"
    elif "航次" in section_title or "船时" in section_title:
        return "open-cruise"
    elif "数据中心" in section_title:
        return "data-center"
    elif "管理" in section_title or "共享" in section_title:
        return "data-management"
    elif "工具" in section_title or "代码" in section_title:
        return "tools-resources"
    return "marine-ai"


def parse_daily_report(html, source_url, source_type):
    """
    解析每日日报页面，提取各板块下的文章条目。

    HTML 结构（当前页面）：
      <section class="section" id="section-1">
        <div class="section-header">
          <span class="section-icon">🤖</span>
          <div>
            <div class="section-title">一、海洋人工智能</div>
            <div class="section-en">Ocean AI</div>
          </div>
          <div class="section-count">3 条</div>
        </div>
        <div class="item-card">
          <div class="item-header">
            <span class="item-badge">[动态]</span>
            <div class="item-title"><a href="...">标题</a></div>
          </div>
          <div class="item-abstract">摘要</div>
        </div>
      </section>

    兼容性：同时支持 <section> 和 <div> 标签，以及 item-card / item 两种 class。
    """
    soup = BeautifulSoup(html, 'html.parser')
    articles = []

    # 从 URL 提取日报日期
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', source_url)
    report_date = (
        f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        if date_match else datetime.now().strftime("%Y-%m-%d")
    )

    # 兼容 <section class="section"> 和 <div class="section"> 两种写法
    sections = soup.find_all(class_='section')

    for section in sections:
        # 获取板块标题
        section_header = section.find('div', class_='section-header')
        section_title_elem = (
            section_header.find('div', class_='section-title')
            if section_header else None
        )
        section_title = section_title_elem.get_text(strip=True) if section_title_elem else ""
        category = get_category(section_title)

        # 兼容 item-card（当前）和 item（旧版）两种 class
        item_cards = section.find_all(class_='item-card')
        if not item_cards:
            item_cards = section.find_all(class_='item')

        for card in item_cards:
            # 找到文章链接（在 item-title > a）
            title_div = card.find('div', class_='item-title')
            if not title_div:
                continue

            link_tag = title_div.find('a')
            if not link_tag:
                continue

            article_url = link_tag.get('href', '').strip()
            if not article_url or article_url.startswith('#'):
                continue

            # 跳过指向本站的链接
            if 'tianyunsu.github.io/ocean-data-daily-report' in article_url:
                continue

            # URL 去重：已存在的 URL 跳过
            if article_url in existing_urls:
                continue

            full_title = link_tag.get_text(strip=True)

            # 解析标题格式：「序号. 来源（日期）：标题」
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

            # 过滤过短标题
            if len(title) < 10:
                continue

            # 摘要
            abstract_elem = card.find('div', class_='item-abstract')
            summary = abstract_elem.get_text(strip=True) if abstract_elem else ""

            articles.append({
                "url": article_url,
                "title": title[:200],
                "summary": summary[:500],
                "date": article_date,
                "reportDate": report_date,
                "source": source_type,
                "sourceName": source,
                "categories": [category],
                "tags": [],
                "fetchedAt": datetime.now().isoformat(),
                # 临时 id，稍后在 main() 统一重编
                "id": f"{report_date}-tmp",
            })

    return articles


def validate_articles_batch(articles, max_workers=8):
    """
    批量验证文章链接有效性（并发）。
    返回 (valid_list, invalid_list)。
    已知可靠域名直接通过，其余发起 HTTP 请求验证。
    """
    valid = []
    invalid = []

    def check(art):
        ok, reason = validate_article_url(art['url'], art['title'], art.get('source', ''))
        return art, ok, reason

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check, a): a for a in articles}
        for future in as_completed(futures):
            art, ok, reason = future.result()
            if ok:
                valid.append(art)
            else:
                invalid.append((art, reason))
                print(f"    [SKIP] {art['title'][:50]} | {reason}")

    return valid, invalid


def deduplicate_by_title(new_articles, existing_articles):
    """
    标题级去重：如果新文章的标题（标准化后）已在现有数据中出现，跳过该新文章。
    标准化：去除标点、转小写，取前 30 字符作为 key。
    """
    def title_key(title):
        t = re.sub(r'[\s\W]+', '', title).lower()
        return t[:30]

    existing_title_keys = {title_key(a['title']) for a in existing_articles}
    deduped = []
    skipped = 0
    for art in new_articles:
        key = title_key(art['title'])
        if key in existing_title_keys:
            skipped += 1
        else:
            deduped.append(art)
            existing_title_keys.add(key)  # 防止新文章内部重复
    if skipped:
        print(f"    [去重] 标题级去重跳过 {skipped} 条重复内容")
    return deduped


# ─── 分类相关性评分（用于跨分类去重时选择最佳分类）──────────────────

CATEGORY_KEYWORDS = {
    'marine-ai': ['ai', '人工智能', '深度学习', 'machine learning', 'neural',
                  'transformer', 'gnn', '预训练', '大模型', 'llm', 'deep learning',
                  '卷积', 'cnn', 'rnn', 'lstm', 'gan', 'diffusion', '强化学习',
                  'fu xi', 'fuxi', 'pangu', 'graphcast', 'aiweather', 'aifs'],
    'digital-twin': ['数字孪生', 'digital twin', 'twin', 'destine', 'destinE',
                     'oceaneye', 'copernicus marine', 'cmems', '耦合', '预报系统',
                     'forecast system', '耦合模型', 'earth system'],
    'visualization': ['可视化', 'vis', 'visualization', '地图', 'map', '图表',
                      'chart', 'dashboard', '平台', 'platform', 'viewer', '3d',
                      '渲染', 'render', '交互', 'interactive', '仪表盘'],
    'data-quality': ['质量', 'quality', 'qa', 'qc', '质控', '校正', 'calibration',
                     'validation', '验证', '偏差', 'bias', '误差', 'error',
                     '准确度', 'accuracy'],
    'data-processing': ['处理', 'processing', 'pipeline', 'workflow', 'etl',
                        '清洗', 'clean', '格式', 'format', '转换', 'convert',
                        '解析', 'parse', 'grib', 'netcdf', 'zarr'],
    'data-management': ['管理', 'management', '共享', 'sharing', 'fair',
                        'policy', '政策', '标准', 'standard', '规范',
                        'metadata', '元数据', 'doi', '编目', 'catalog'],
    'open-cruise': ['航次', 'cruise', '船时', 'expedition', '探险', '考察',
                    '科考船', 'research vessel', 'okeanos', 'nautilus',
                    'schmidt', '潜水器', 'rov', 'hoV', 'submersible'],
    'data-center': ['数据中心', 'data center', 'database', '数据库', '仓库',
                    'repository', '归档', 'archive', 'pangaea', 'ncei',
                    'podaac', '存储', 'storage', '基础设施', 'infrastructure'],
    'tools-resources': ['工具', 'tool', '代码', 'code', '开源', 'open source',
                        'github', 'python', 'package', '包', '库', 'library',
                        'api', 'sdk', '教程', 'tutorial', '文档', 'doc'],
}


def score_category_relevance(title, category):
    """根据标题关键词给分类相关性打分，分数越高越相关"""
    title_lower = title.lower()
    score = 0
    for kw in CATEGORY_KEYWORDS.get(category, []):
        if kw.lower() in title_lower:
            score += 1
    return score


def full_deduplicate(all_articles):
    """
    全量去重：对所有文章（已有 + 新增）执行统一去重。

    去重策略（按优先级）：
    1. URL 去重：相同 URL 只保留一条。跨分类时，保留分类相关性评分最高的一条。
    2. 标题去重：相同标准化标题（即使 URL 不同）只保留一条。

    返回去重后的文章列表。
    """
    if not all_articles:
        return all_articles

    removed = 0

    # ── 第一步：URL 去重（含跨分类选择）──
    by_url = {}
    for art in all_articles:
        url = art.get('url', '').strip()
        if not url:
            continue
        if url not in by_url:
            by_url[url] = []
        by_url[url].append(art)

    url_deduped = []
    for url, arts_with_same_url in by_url.items():
        if len(arts_with_same_url) == 1:
            url_deduped.append(arts_with_same_url[0])
        else:
            # 跨分类去重：选择分类相关性最高的那条
            best = max(arts_with_same_url, key=lambda a: score_category_relevance(
                a.get('title', ''), a.get('categories', [''])[0]))
            url_deduped.append(best)
            removed += len(arts_with_same_url) - 1

    # ── 第二步：标题去重（URL 不同但标题相同）──
    def title_key(title):
        t = re.sub(r'[\s\W]+', '', title).lower()
        return t[:50]

    seen_titles = {}
    final = []
    for art in sorted(url_deduped, key=lambda x: x.get('reportDate', ''), reverse=True):
        key = title_key(art.get('title', ''))
        if not key:
            final.append(art)
            continue
        if key in seen_titles:
            removed += 1
            continue
        seen_titles[key] = True
        final.append(art)

    if removed > 0:
        print(f"    [全量去重] 移除 {removed} 条重复记录（URL重复 + 标题重复）")

    return final


def main():
    """主函数：增量抓取 + 链接验证 + 去重合并"""
    print("=" * 60)
    print("海洋AI进展汇总 - 增量抓取 v7")
    print(f"策略: 抓取最近 {DAYS_TO_FETCH} 天 | URL去重 | 标题去重 | 链接验证")
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
            print(f"\n[现有数据] 共 {len(existing_articles)} 条记录，{len(existing_urls)} 个唯一 URL")

    # 计算日期范围
    today = datetime.now()
    cutoff_date = (today - timedelta(days=DAYS_TO_FETCH)).strftime('%Y-%m-%d')
    print(f"[日期范围] {cutoff_date} 至今\n")

    raw_new_articles = []  # 未验证的新文章

    # ─── 抓取主站 ───────────────────────────────────────────────
    print(f"[1/2] 正在抓取主站: {MAIN_URL}")
    main_html = fetch_page(MAIN_URL)
    if main_html:
        archive_links = get_archive_links_with_date(main_html, MAIN_URL)
        recent_links = [l for l in archive_links if l['date'] >= cutoff_date]
        print(f"   找到 {len(archive_links)} 个日报（归档去重后），最近 {DAYS_TO_FETCH} 天: {len(recent_links)} 个")

        for i, link_info in enumerate(recent_links):
            print(f"   抓取: {link_info['url']}")
            html = fetch_page(link_info['url'])
            if html:
                articles = parse_daily_report(html, link_info['url'], "main")
                raw_new_articles.extend(articles)
                print(f"     解析到 {len(articles)} 条（已过 URL 去重）")
    else:
        print("   [ERROR] 主站首页获取失败")

    # ─── 抓取补充站 ──────────────────────────────────────────────
    print(f"\n[2/2] 正在抓取补充站: {SUPPLEMENT_URL}")
    supp_html = fetch_page(SUPPLEMENT_URL)
    if supp_html:
        archive_links = get_archive_links_with_date(supp_html, SUPPLEMENT_URL)
        recent_links = [l for l in archive_links if l['date'] >= cutoff_date]
        print(f"   找到 {len(archive_links)} 个日报（归档去重后），最近 {DAYS_TO_FETCH} 天: {len(recent_links)} 个")

        for i, link_info in enumerate(recent_links):
            print(f"   抓取: {link_info['url']}")
            html = fetch_page(link_info['url'])
            if html:
                articles = parse_daily_report(html, link_info['url'], "supplement")
                raw_new_articles.extend(articles)
                print(f"     解析到 {len(articles)} 条（已过 URL 去重）")
    else:
        print("   [ERROR] 补充站首页获取失败")

    print(f"\n[小计] 解析到 {len(raw_new_articles)} 条新记录（URL 未重复）")

    # ─── 标题级去重 ──────────────────────────────────────────────
    print("\n[去重] 执行标题级去重...")
    deduped_new = deduplicate_by_title(raw_new_articles, existing_articles)
    print(f"   去重后: {len(deduped_new)} 条待验证")

    # ─── 链接有效性验证 ──────────────────────────────────────────
    if deduped_new:
        print(f"\n[验证] 验证 {len(deduped_new)} 条新文章链接...")
        valid_new, invalid_new = validate_articles_batch(deduped_new, max_workers=6)
        print(f"   有效: {len(valid_new)} | 无效/跳过: {len(invalid_new)}")
    else:
        valid_new = []
        invalid_new = []

    # ─── 合并 & 全量去重 & 排序 ──────────────────────────────────
    all_articles = valid_new + existing_articles

    # 全量去重：对已有 + 新增数据统一去重（URL 去重 + 标题去重 + 跨分类去重）
    before_dedup = len(all_articles)
    all_articles = full_deduplicate(all_articles)
    after_dedup = len(all_articles)
    if before_dedup != after_dedup:
        print(f"\n[全量去重] {before_dedup} → {after_dedup} 条（移除 {before_dedup - after_dedup} 条重复）")

    all_articles.sort(key=lambda x: (x.get('date', ''), x.get('reportDate', '')), reverse=True)

    # 重新编号（保证 id 唯一稳定）
    for i, art in enumerate(all_articles):
        art['id'] = f"{art.get('date', 'unknown')}-{i + 1:04d}"

    # ─── 统计 ─────────────────────────────────────────────────────
    new_count = len(valid_new)
    total_count = len(all_articles)

    print("\n" + "=" * 60)
    if new_count > 0:
        print(f"✅ 增量抓取完成！")
        print(f"   新增: {new_count} 条 | 过滤无效: {len(invalid_new)} 条")
        print(f"   总计: {total_count} 条")
    else:
        print("📭 今日无新增有效进展")
        print(f"   现有: {total_count} 条")

    category_stats = {}
    for art in all_articles:
        for cat in art.get('categories', []):
            category_stats[cat] = category_stats.get(cat, 0) + 1

    print("\n分类统计:")
    for cat, count in sorted(category_stats.items(), key=lambda x: -x[1]):
        print(f"  - {cat}: {count} 条")

    # ─── 保存数据 ─────────────────────────────────────────────────
    output_data = {
        "articles": all_articles,
        "lastUpdated": datetime.now().isoformat(),
        "stats": {
            "total": total_count,
            "newToday": new_count,
            "byCategory": category_stats,
            "validation": {
                "newCandidates": len(raw_new_articles),
                "afterTitleDedup": len(deduped_new),
                "validNew": new_count,
                "invalidNew": len(invalid_new),
            }
        }
    }

    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存至: {data_file}")

    # 打印新增预览
    if valid_new:
        print(f"\n新增进展（前5条）:")
        for art in valid_new[:5]:
            print(f"\n  [{art['reportDate']}·{art['source']}] {art['title'][:70]}")
            print(f"    {art['url'][:80]}")

    return output_data


if __name__ == "__main__":
    main()
