# Git远程仓库设置指南

## ✅ 当前状态

Git版本管理已建立：
- ✅ 本地Git仓库已初始化
- ✅ v1.1版本已提交
- ✅ 版本标签已创建（v1.1）
- ✅ 34个文件已纳入版本控制

## 🎯 将代码推送到远程仓库

### 方案选择

| 平台 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **GitHub** | 最流行、生态好 | 国内访问慢 | ⭐⭐⭐⭐⭐ |
| **Gitee（码云）** | 国内快、中文友好 | 生态较小 | ⭐⭐⭐⭐ |
| **GitLab** | 功能强大 | 相对复杂 | ⭐⭐⭐ |
| **自建Git服务器** | 完全私有 | 需要维护 | ⭐⭐ |

推荐：**Gitee**（国内）或 **GitHub**（国际）

---

## 📝 方案A：使用GitHub（国际推荐）

### 1. 创建GitHub仓库

1. 访问 https://github.com
2. 点击右上角 "+" → "New repository"
3. 填写信息：
   - Repository name: `ai-video-to-audio`
   - Description: `AI视频转中文播客工具`
   - 选择 **Private**（如果不想公开）
   - **不要**勾选 "Initialize with README"（本地已有）
4. 点击 "Create repository"

### 2. 连接远程仓库

GitHub会显示命令，复制以下命令执行：

```bash
# 添加远程仓库（替换成你的用户名）
git remote add origin https://github.com/YOUR_USERNAME/ai-video-to-audio.git

# 设置主分支名称
git branch -M main

# 推送代码和标签
git push -u origin main
git push origin --tags
```

### 3. 验证

访问你的GitHub仓库页面，应该能看到所有代码和v1.1标签。

### 4. 后续使用

```bash
# 每次修改后推送
git add .
git commit -m "描述你的修改"
git push

# 推送标签（新版本时）
git push origin v1.2
```

---

## 📝 方案B：使用Gitee（国内推荐）

### 1. 创建Gitee仓库

1. 访问 https://gitee.com
2. 点击右上角 "+" → "新建仓库"
3. 填写信息：
   - 仓库名称: `ai-video-to-audio`
   - 仓库介绍: `AI视频转中文播客工具`
   - 是否开源: **私有**（如果不想公开）
   - **不要**勾选 "使用Readme文件初始化仓库"
4. 点击 "创建"

### 2. 连接远程仓库

```bash
# 添加远程仓库（替换成你的用户名）
git remote add origin https://gitee.com/YOUR_USERNAME/ai-video-to-audio.git

# 设置主分支名称
git branch -M main

# 推送代码和标签
git push -u origin main
git push origin --tags
```

### 3. 验证

访问你的Gitee仓库页面，应该能看到所有代码和v1.1标签。

---

## 🔐 认证配置

### SSH密钥配置（推荐）

使用SSH可以避免每次输入密码。

#### 1. 生成SSH密钥

```bash
# 生成新密钥（替换你的邮箱）
ssh-keygen -t ed25519 -C "your_email@example.com"

# 一路回车，使用默认位置
```

#### 2. 查看公钥

```bash
cat ~/.ssh/id_ed25519.pub
```

复制输出的内容。

#### 3. 添加到GitHub/Gitee

**GitHub**：
1. 访问 https://github.com/settings/keys
2. 点击 "New SSH key"
3. 粘贴公钥，点击 "Add SSH key"

**Gitee**：
1. 访问 https://gitee.com/profile/sshkeys
2. 点击 "添加公钥"
3. 粘贴公钥，点击 "确定"

#### 4. 修改远程地址为SSH

```bash
# 查看当前远程地址
git remote -v

# 修改为SSH地址（GitHub）
git remote set-url origin git@github.com:YOUR_USERNAME/ai-video-to-audio.git

# 或修改为SSH地址（Gitee）
git remote set-url origin git@gitee.com:YOUR_USERNAME/ai-video-to-audio.git
```

#### 5. 测试连接

```bash
# 测试GitHub
ssh -T git@github.com

# 测试Gitee
ssh -T git@gitee.com
```

---

## 📖 常用Git命令

### 日常开发

```bash
# 查看状态
git status

# 查看修改
git diff

# 添加文件
git add .              # 添加所有修改
git add file.py        # 添加特定文件

# 提交
git commit -m "描述修改内容"

# 推送到远程
git push

# 拉取远程更新
git pull
```

### 版本管理

```bash
# 查看所有版本标签
git tag

# 查看特定标签信息
git show v1.1

# 创建新版本标签
git tag -a v1.2 -m "v1.2: 第二层TTS优化"

# 推送标签
git push origin v1.2

# 推送所有标签
git push origin --tags

# 删除标签（本地）
git tag -d v1.2

# 删除标签（远程）
git push origin --delete v1.2
```

### 版本回退

```bash
# 查看提交历史
git log --oneline

# 回退到特定版本（保留修改）
git reset --soft v1.1

# 回退到特定版本（丢弃修改）⚠️
git reset --hard v1.1

# 回退到上一个版本
git reset --hard HEAD^

# 查看特定版本的文件
git show v1.1:utils/translator.py

# 恢复特定版本的文件
git checkout v1.1 -- utils/translator.py
```

### 分支管理

```bash
# 查看所有分支
git branch -a

# 创建新分支
git branch feature/tts-optimization

# 切换分支
git checkout feature/tts-optimization

# 创建并切换分支
git checkout -b feature/tts-optimization

# 合并分支
git checkout main
git merge feature/tts-optimization

# 删除分支
git branch -d feature/tts-optimization
```

---

## 🚀 推荐工作流

### 开发新功能

```bash
# 1. 创建功能分支
git checkout -b feature/tts-layer2

# 2. 进行开发
# ... 修改代码 ...

# 3. 提交更改
git add .
git commit -m "实现TTS第二层优化"

# 4. 推送到远程
git push -u origin feature/tts-layer2

# 5. 测试通过后合并到主分支
git checkout main
git merge feature/tts-layer2

# 6. 创建版本标签
git tag -a v1.2 -m "v1.2: 第二层TTS优化完成"

# 7. 推送主分支和标签
git push origin main
git push origin v1.2
```

### 紧急修复

```bash
# 1. 创建修复分支
git checkout -b hotfix/proxy-issue

# 2. 修复问题
# ... 修改代码 ...

# 3. 提交
git add .
git commit -m "修复: 代理连接问题"

# 4. 合并到主分支
git checkout main
git merge hotfix/proxy-issue

# 5. 推送
git push origin main

# 6. 删除修复分支
git branch -d hotfix/proxy-issue
```

---

## 📋 .gitignore 配置

已为您配置好忽略文件：

```gitignore
# Python
__pycache__/
*.pyc
venv/

# 敏感信息
.env

# 输出文件
output/
*.mp3
*.mp4

# 系统文件
.DS_Store
```

---

## ⚠️ 注意事项

### 1. 敏感信息保护

**重要**：`.env` 文件已被忽略，不会上传到远程仓库。

如果不小心提交了敏感信息：

```bash
# 从Git历史中移除
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# 强制推送（慎用）
git push origin --force --all
git push origin --force --tags
```

### 2. 大文件处理

Git不适合管理大文件（如音频、视频）。如需版本管理大文件：

- 使用Git LFS（Large File Storage）
- 或将输出文件存储在其他地方

### 3. 协作开发

如果多人协作：

```bash
# 拉取最新代码
git pull

# 如有冲突，解决后提交
git add .
git commit -m "解决冲突"
git push
```

---

## 🎯 快速开始命令（复制粘贴）

### GitHub

```bash
# 1. 添加远程仓库（替换YOUR_USERNAME）
git remote add origin https://github.com/YOUR_USERNAME/ai-video-to-audio.git

# 2. 推送代码
git branch -M main
git push -u origin main
git push origin --tags

# 3. 验证
git remote -v
```

### Gitee

```bash
# 1. 添加远程仓库（替换YOUR_USERNAME）
git remote add origin https://gitee.com/YOUR_USERNAME/ai-video-to-audio.git

# 2. 推送代码
git branch -M main
git push -u origin main
git push origin --tags

# 3. 验证
git remote -v
```

---

## 📚 更多学习资源

- [Git官方文档](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Gitee帮助文档](https://gitee.com/help)
- [Git简明指南](https://rogerdudler.github.io/git-guide/index.zh.html)

---

## 🆘 常见问题

### Q1: push时提示403错误？
A: 检查用户名和密码，或配置SSH密钥。

### Q2: 如何撤销最后一次提交？
A: `git reset --soft HEAD^` 保留修改，或 `git reset --hard HEAD^` 丢弃修改。

### Q3: 如何查看某个版本的代码？
A: `git checkout v1.1` 或 `git show v1.1:file.py`

### Q4: 如何同步远程的新分支？
A: `git fetch origin` 然后 `git checkout -b branch-name origin/branch-name`

---

**当前Git状态**：
- ✅ 本地仓库已建立
- ✅ v1.1版本已提交并打标签
- ⏳ 等待连接远程仓库

**下一步**：选择GitHub或Gitee，按照上面的步骤连接远程仓库。
