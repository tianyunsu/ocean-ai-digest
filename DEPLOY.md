# 部署到 GitHub Pages 指南

## 步骤 1: 创建 GitHub 仓库

1. 登录 GitHub (https://github.com)
2. 点击右上角 **"+"** → **"New repository"**
3. 填写仓库信息：
   - **Repository name**: `ocean-ai-digest` (或您喜欢的名称)
   - **Description**: 海洋AI进展汇总网站
   - **选择 Private 或 Public** (公开仓库才能用 GitHub Pages)
   - **不要勾选** "Add a README file" (我们已经有了)

## 步骤 2: 上传文件到仓库

### 方法 A: 使用 GitHub 网页上传（推荐新手）

1. 在仓库页面，点击 **"uploading an existing files"**
2. 将 `ocean-ai-digest` 文件夹内的**所有文件**拖拽到上传区域
3. 点击 **"Commit changes"**

### 方法 B: 使用 Git 命令行

```bash
# 在本地克隆空仓库
git clone https://github.com/您的用户名/ocean-ai-digest.git

# 将项目文件复制到克隆的文件夹
# (Windows) 复制 ocean-ai-digest 文件夹内所有内容到仓库文件夹

# 提交并推送
cd ocean-ai-digest
git add .
git commit -m "Initial commit"
git push origin main
```

## 步骤 3: 启用 GitHub Pages

1. 在仓库页面，点击 **Settings** (设置)
2. 滚动到 **"Pages"** 部分
3. 配置：
   - **Source**: Select **"Deploy from a branch"**
   - **Branch**: Select **"main"** 和 **"/ (root)"**
   - 点击 **"Save"**

4. 等待 1-2 分钟，网站将自动部署

5. 您的网站将在以下地址可访问：
   ```
   https://您的用户名.github.io/ocean-ai-digest/
   ```

## 步骤 4: 自动更新配置

### 配置 GitHub Personal Access Token (用于自动更新)

1. 在 GitHub 点击头像 → **Settings**
2. 左侧菜单: **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. 点击 **"Generate new token"**
4. 配置:
   - **Note**: Ocean AI Digest Update
   - **Expiration**: 建议 30 天或更长
   - **Select scopes**: 勾选 **"repo"** (完整仓库访问)
5. 点击 **"Generate token"**
6. **重要**: 复制并保存生成的 token（一段时间后会隐藏）

7. 在您的仓库中：
   - 点击 **Settings** → **Secrets and variables** → **Actions**
   - 点击 **"New repository secret"**
   - **Name**: `GH_TOKEN`
   - **Secret**: 粘贴您刚才生成的 token
   - 点击 **"Add secret"**

### 测试自动更新

1. 在仓库页面，点击 **Actions** 标签
2. 点击左侧 **"Update Ocean AI Digest"**
3. 点击 **"Run workflow"** → **"Run workflow"**
4. 等待执行完成，查看结果

## 自定义域名（可选）

如果您有自定义域名：

1. 在仓库 **Settings** → **Pages** → **Custom domain**
2. 输入您的域名（如 `ocean.example.com`）
3. 在您的域名 DNS 设置中添加：
   - CNAME 记录指向 `您的用户名.github.io`

## 验证部署成功

部署完成后，访问您的网站地址，应该能看到：

✅ 首页显示 9 个研究方向分类卡片
✅ 点击分类可以查看该方向的进展
✅ 全部进展页面可以搜索和筛选

---

## 故障排除

### 网页显示 404 错误
- 确认 GitHub Pages 已正确启用
- 确认仓库中有 `index.html` 文件
- 等待最多 5 分钟让部署完成

### 自动更新失败
- 检查 `GH_TOKEN` secret 是否正确配置
- 查看 Actions 日志中的错误信息

### 数据未更新
- 点击 Actions 手动运行更新工作流
- 检查网络连接和源站是否可访问
