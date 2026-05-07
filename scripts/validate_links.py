# -*- coding: utf-8 -*-
"""
验证文章链接有效性并删除无效链接
"""

import json
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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

def validate_article_url(article):
    """
    验证单个文章链接有效性
    返回: (article, is_valid, reason)
    """
    url = article['url']
    title = article['title']
    
    # 检查域名是否跳过验证
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    for skip_domain in SKIP_VALIDATION_DOMAINS:
        if skip_domain in domain:
            return article, True, "跳过验证（已知可靠域名）"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        # 检查HTTP状态码
        if response.status_code >= 400:
            return article, False, f"页面失效 (HTTP {response.status_code})"
        
        if response.status_code >= 300:
            final_url = response.url
            if final_url != url and any(hp in final_url.lower() for hp in HOME_PAGE_KEYWORDS):
                return article, False, f"重定向至综合页面: {final_url[:60]}"
        
        # 解析页面内容
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
        except:
            return article, False, "页面解析失败"
        
        # 获取页面标题
        page_title = ""
        title_tag = soup.find('title')
        if title_tag:
            page_title = title_tag.get_text(strip=True).lower()
        
        # 检查是否为首页或综合页面
        if page_title:
            for keyword in HOME_PAGE_KEYWORDS:
                if keyword.lower() in page_title:
                    if len(page_title) < 50:
                        return article, False, f"判定为首页/综合页面 (标题: {page_title[:40]})"
        
        # 检查标题是否与文章标题相关
        if title and page_title:
            title_keywords = title.lower()
            title_keywords = re.sub(r'[\[\]()【】（）""''""《》<>]', ' ', title_keywords)
            title_keywords = re.sub(r'\s+', ' ', title_keywords).strip()
            
            key_phrase = title_keywords[:20] if len(title_keywords) >= 20 else title_keywords
            
            if len(key_phrase) >= 10:
                stop_words = ['the', 'a', 'an', 'of', 'in', 'on', 'at', 'for', 'to', 'and', 'or', 'with', 'by']
                words = [w for w in key_phrase.split() if w not in stop_words and len(w) >= 3]
                
                if words:
                    matched = False
                    for word in words[:3]:
                        if word in page_title:
                            matched = True
                            break
                    
                    if not matched:
                        return article, False, f"标题不符 (页面: {page_title[:40]}... vs 文章: {title[:25]}...)"
        
        return article, True, "验证通过"
        
    except requests.exceptions.Timeout:
        return article, False, "请求超时"
    except requests.exceptions.ConnectionError:
        return article, False, "连接失败"
    except Exception as e:
        return article, False, f"验证错误: {str(e)[:30]}"

def main():
    print("=" * 60)
    print("文章链接有效性验证")
    print("=" * 60)
    
    # 读取数据
    input_path = '_data/articles.json'
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    articles = data['articles']
    print(f"\n待验证文章数: {len(articles)}")
    
    # 验证结果统计
    valid_articles = []
    invalid_count = 0
    skipped_count = 0
    invalid_list = []
    
    print("\n开始验证...")
    
    # 使用线程池并行验证
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(validate_article_url, art): art for art in articles}
        
        for i, future in enumerate(as_completed(futures)):
            article, is_valid, reason = future.result()
            
            if is_valid:
                valid_articles.append(article)
            else:
                invalid_count += 1
                invalid_list.append({
                    'id': article['id'],
                    'title': article['title'],
                    'url': article['url'],
                    'reason': reason
                })
                if '跳过' in reason:
                    skipped_count += 1
            
            # 进度显示
            if (i + 1) % 50 == 0 or (i + 1) == len(articles):
                print(f"  进度: {i+1}/{len(articles)} | 有效: {len(valid_articles)} | 无效: {invalid_count}")
    
    # 统计
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)
    print(f"✓ 有效链接: {len(valid_articles)} 条")
    print(f"✗ 无效链接: {invalid_count} 条")
    
    # 分类统计
    if invalid_list:
        print("\n无效链接详情:")
        print("-" * 60)
        for item in invalid_list:
            print(f"\n[{item['id']}] {item['title'][:50]}")
            print(f"  URL: {item['url'][:80]}")
            print(f"  原因: {item['reason']}")
    
    # 统计分类变化
    original_stats = {}
    for art in articles:
        for cat in art.get('categories', []):
            original_stats[cat] = original_stats.get(cat, 0) + 1
    
    new_stats = {}
    for art in valid_articles:
        for cat in art.get('categories', []):
            new_stats[cat] = new_stats.get(cat, 0) + 1
    
    print("\n" + "=" * 60)
    print("分类统计变化")
    print("=" * 60)
    all_cats = set(original_stats.keys()) | set(new_stats.keys())
    for cat in sorted(all_cats):
        orig = original_stats.get(cat, 0)
        new = new_stats.get(cat, 0)
        diff = new - orig
        diff_str = f"({diff:+d})" if diff != 0 else ""
        print(f"  {cat}: {orig} → {new} {diff_str}")
    
    # 保存结果
    output_data = {
        "articles": valid_articles,
        "lastUpdated": datetime.now().isoformat(),
        "stats": {
            "total": len(valid_articles),
            "byCategory": new_stats,
            "validation": {
                "originalCount": len(articles),
                "validCount": len(valid_articles),
                "invalidCount": invalid_count,
                "skippedCount": skipped_count
            }
        }
    }
    
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print(f"数据已更新: {input_path}")
    print(f"删除无效链接: {invalid_count} 条")
    print(f"保留有效链接: {len(valid_articles)} 条")
    print("=" * 60)
    
    return valid_articles, invalid_list

if __name__ == "__main__":
    main()
