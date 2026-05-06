# 海洋AI进展汇总网站

聚合海洋AI技术日报与补充日报，按研究方向分类整理。

## 项目结构

```
ocean-ai-digest/
├── index.html              # 首页
├── all.html                # 全部进展
├── assets/                 # 资源文件
├── categories/             # 9个分类页面
│   ├── marine-ai.html
│   ├── digital-twin.html
│   ├── visualization.html
│   ├── data-quality.html
│   ├── data-processing.html
│   ├── data-management.html
│   ├── open-cruise.html
│   ├── data-center.html
│   └── tools-resources.html
├── _data/                  # 数据文件
│   ├── articles.json       # 文章数据
│   └── categories.json     # 分类配置
├── scripts/                # 脚本
│   ├── fetch_articles.py   # 数据抓取
│   └── generate_pages.py   # 页面生成
└── .github/workflows/      # CI/CD
    └── update.yml          # 自动更新
```

## 9个研究方向

1. 海洋人工智能
2. 海洋数字孪生
3. 海洋可视化
4. 海洋数据质量
5. 海洋数据处理
6. 数据管理与共享服务
7. 开放航次/船时共享
8. 海洋数据中心
9. 工具与代码资源

## 快速开始

### 本地运行

1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 抓取数据：`python scripts/fetch_articles.py`
4. 生成页面：`python scripts/generate_pages.py`
5. 用浏览器打开 `index.html`

### 部署

推荐部署到 GitHub Pages：
1. Fork 本仓库
2. 启用 GitHub Pages
3. GitHub Actions 将自动每日更新

## 自动更新

- 定时更新：每天北京时间 08:00
- 手动触发：在 GitHub Actions 页面点击 "Run workflow"

## 数据来源

- [海洋AI技术日报](https://tianyunsu.github.io/ocean-data-daily-report/)
- [补充日报](https://tianyunsu.github.io/ocean-data-daily-report/supplement/)
