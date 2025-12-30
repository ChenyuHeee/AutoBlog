<div align="center">

# AutoBlog

一个使用 Python 编写的轻量级静态博客生成器：将 `source/` 中的 Markdown 构建为 `public/` 下的可部署网站，可直接托管在 GitHub Pages。

<!-- 仓库：ChenyuHeee/AutoBlog -->

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/github/license/ChenyuHeee/AutoBlog?style=for-the-badge)
![Repo Size](https://img.shields.io/github/repo-size/ChenyuHeee/AutoBlog?style=for-the-badge)
![Top Language](https://img.shields.io/github/languages/top/ChenyuHeee/AutoBlog?style=for-the-badge)
![Languages](https://img.shields.io/github/languages/count/ChenyuHeee/AutoBlog?style=for-the-badge)
![Stars](https://img.shields.io/github/stars/ChenyuHeee/AutoBlog?style=for-the-badge)
![Forks](https://img.shields.io/github/forks/ChenyuHeee/AutoBlog?style=for-the-badge)
![Issues](https://img.shields.io/github/issues/ChenyuHeee/AutoBlog?style=for-the-badge)
![Commit Activity](https://img.shields.io/github/commit-activity/m/ChenyuHeee/AutoBlog?style=for-the-badge)
![Contributors](https://img.shields.io/github/contributors/ChenyuHeee/AutoBlog?style=for-the-badge)
![Last Commit](https://img.shields.io/github/last-commit/ChenyuHeee/AutoBlog?style=for-the-badge)

[![README 中文](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-1f6feb?style=for-the-badge)](README.md)
[![README EN](https://img.shields.io/badge/README-English-1f6feb?style=for-the-badge)](README_en.md)

</div>

## 这是什么？（给想搭博客的你）

AutoBlog 用来把你写的 Markdown 文章生成一个完整的静态博客站点，并且可以一条命令部署到 GitHub Pages。

你会得到：

- 文章页 + 首页列表
- 标签页、归档页、站内搜索
- RSS + sitemap（配置 `site_url` 后自动生成）

你只需要：用 Markdown 写文章，执行构建/部署命令。

## 5 分钟上手：从 0 到上线

### 0）准备

- 安装 Python 3.10+
- 本地有 Git
- 有一个 GitHub 仓库（用于承载博客）

### 1）克隆项目

```bash
git clone https://github.com/ChenyuHeee/AutoBlog
cd AutoBlog
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2）推荐：使用桌面端编辑器（编辑 + 预览 + 构建）

如果你不想手动改配置/命令行构建，可以直接用桌面端 App 来管理：编辑 `config.yaml`、编辑 Markdown 并实时预览、编辑主题文件、点击构建并打开本地预览。

#### Desktop App (PySide6)

安装依赖：

```bash
pip install -r requirements.txt -r requirements_desktop.txt
```

启动：

```bash
python run_desktop.py
```

说明：
- “构建”会复用 build.py 的逻辑生成 public/
- “启动预览服务”会在本机起一个静态服务器，然后用系统浏览器打开

（继续下一步：创建站点配置）

### 3）创建你的站点配置

把示例配置复制为正式配置：

```bash
cp source/config.yaml.example.yaml source/config.yaml
```

然后编辑 `source/config.yaml`（下面是一个最小示例，按你的仓库信息修改）：

```yaml
nav:
  - label: 首页
    url: /
  - label: 标签
    url: /tags/
  - label: GitHub
    url: https://github.com/YourName/YourRepo

social:
  - label: 邮箱：you@example.com
    url: mailto:you@example.com
    icon: mail
  - label: GitHub @YourName
    url: https://github.com/YourName
    icon: github

github_repo: your-user/your-repo
github_branch: gh-pages
github_remote: origin

# 关键：base_url 决定 GitHub Pages 路径
# 1) 如果是“项目页”（https://your-user.github.io/your-repo/）：
base_url: /your-repo/
# 2) 如果是“个人主页”（https://your-user.github.io/）：
# base_url: /

# 推荐：填上绝对站点地址以生成 RSS/sitemap 的绝对链接
# site_url: https://your-user.github.io/your-repo/
```

### 4）写第一篇文章

在 `source/posts/` 下新建一个 Markdown，例如：

```markdown
---
title: "Hello AutoBlog"
date: 2025-12-29
slug: hello
description: "我的第一篇博客。"
---

这里写正文。
```

### 5）本地预览

推荐：用桌面端编辑器直接点击“构建”+“打开预览”。

命令行方式：

```bash
python3 build.py
```

构建完成后，打开 `public/index.html` 即可预览。

### 6）部署到 GitHub Pages

```bash
python3 build.py --deploy
```

然后到 GitHub 仓库设置里启用 Pages：

- Source 选择 `github_branch`（默认示例是 `gh-pages`）
- 目录选择仓库根目录（root）

几分钟后即可通过 Pages 地址访问。

## 常见踩坑（最重要的 2 个）

1. 页面路径不对/资源 404：优先检查 `base_url` 是否正确（项目页通常是 `/<repo>/`）。
2. RSS / sitemap 里链接不对：补上 `site_url`（带 `https://` 且以 `/` 结尾）。

## 更多功能（按需看）

- 文件夹元数据：`source/posts/**/_meta.yaml` 可以批量追加 tags / 默认字段
- 合集（collection）：把一个目录折叠成首页一张合集卡片
- AI 摘要：缺少 `description` 时可用 DeepSeek 自动生成并写回

<details>
<summary>高级配置（config.yaml 参考）</summary>

权威参考：`source/config.yaml.example.yaml`（建议从它复制一份作为 `source/config.yaml` 再改）。

### URL / GitHub Pages

- `github_repo`：`owner/repo`，用于推导默认 Pages 地址与推送目标
- `github_branch`：承载静态文件的分支（常用 `gh-pages`）
- `github_remote`：本地 git remote 名称（默认 `origin`）
- `github_remote_url`：显式指定推送地址（不想依赖本地 remote 或 `github_repo` 时用）
- `base_url`：资源与路由前缀（项目页通常 `/<repo>/`；个人主页通常 `/`）
- `site_url`：站点绝对地址（用于 RSS/sitemap 的绝对链接，必须以 `https://` 开头并以 `/` 结尾）

### 导航栏（可选，自定义）

不配置时会自动生成“首页/归档/标签/页面”。如果你想完全自定义：

```yaml
nav_links:
  - label: 首页
    url: /
  - label: 标签
    url: /tags/
  - label: GitHub
    url: https://github.com/ChenyuHeee/AutoBlog
```

### RSS / Sitemap

- `rss_enabled: false`：关闭 RSS（同时会影响页面中 RSS 相关输出）

### 侧栏联系方式

```yaml
contacts:
  - label: 邮箱：you@example.com
    url: mailto:you@example.com
    icon: mail
    note: 学习交流欢迎来信
  - label: GitHub @YourName
    url: https://github.com/YourName
    icon: github
```

### 背景音乐播放器

```yaml
background_music:
  enabled: true
  src: media/your.mp3
  title: "Song Title"
  artist: "Artist"
  cover: media/cover.jpg
  autoplay: false
  start_muted: true
```

`src/cover` 对应的是 `source/assets/` 下的相对路径（例如文件放在 `source/assets/media/your.mp3`，这里写 `media/your.mp3`）。

### AI 摘要（DeepSeek）

当文章没写 `description` 时可自动生成摘要并写回 Markdown。

```yaml
ai_summary:
  provider: deepseek
  api_key: ""  # 推荐使用环境变量 DEEPSEEK_API_KEY
  model: deepseek-chat
  endpoint: https://api.deepseek.com/v1/chat/completions
  temperature: 0.2
  max_input_chars: 6000
  max_tokens: 200
  max_output_chars: 120
```

</details>

## 可视化管理后台（本地 Web UI）

如果你想通过界面管理 `config.yaml`、编辑文章并实时预览、以及修改主题模板/资源，可以启动本项目自带的本地管理后台。

安装依赖：

```bash
pip install -r requirements.txt -r requirements_admin.txt
```

启动：

```bash
python3 -m uvicorn admin.app:app --reload --port 5177
```

打开：

- 管理后台：`http://127.0.0.1:5177/`
- 构建后的站点预览：`http://127.0.0.1:5177/preview/`

提示：后台会直接修改仓库里的源文件（例如 `source/config.yaml`、`source/posts/**.md`、`templates/*.html`），建议配合 Git 使用。

<details>
<summary>高级写作（Front Matter / _meta.yaml / 合集 / 置顶）</summary>

### 文章 Front Matter

文章（`source/posts/**/*.md`）支持 YAML Front Matter，例如：

```yaml
---
title: "我的第一篇文章"
date: 2025-12-29
slug: my-first-post
description: "一句话摘要（用于首页卡片/SEO）。"
excerpt: "可选：更短的摘要，或给 RSS/列表用。"
tags: [AIOps, 论文]
draft: false

# 置顶（两种写法都支持）：
pinned: true
# 或 pinned: 10  （数字也会被当成置顶，并作为优先级参考）
pinned_priority: 0
---
```

要点：

- `tags` 支持数组，或字符串（支持逗号/分号/斜杠分隔）。
- `draft: true` 默认不会输出（用 `python3 build.py --drafts` 才会包含）。
- `pinned: true` 置顶；`pinned_priority` 越小越靠前；不填默认当作 `0`。

### 目录级 `_meta.yaml`（批量默认值 + 批量标签）

在 `source/posts/` 的任意子目录里放 `_meta.yaml`，它会对该目录及所有子目录文章生效，并且会沿目录层级叠加：

```text
source/posts/
  _meta.yaml
  aiops/
    _meta.yaml
    intro.md
```

支持两类能力：

1) `tags`：会和文章自身 `tags` 合并，去重（大小写不敏感），并且会把合并结果写回到文章 Front Matter，保证下次构建一致。

2) 其它键：作为“默认值”填充到文章 Front Matter（仅当文章缺少该字段时才会填充），同样可能写回文件。

示例：

```yaml
tags: [AIOps]
draft: false
```

### 合集（collection）

在 `_meta.yaml` 中配置 `collection`，可以把一个目录折叠成首页的一张合集卡片，并生成合集列表页面。

最简单：

```yaml
collection: true
```

完整写法（可覆盖标题/描述/排序/标签）：

```yaml
collection:
  enabled: true
  title: "AIOps 学习笔记"
  description: "论文精读、项目复现与实践记录。"
  order: 10
  tags: [AIOps, 论文]
```

关闭合集（对某个子目录禁用）：

```yaml
collection: false
# 或
collection:
  enabled: false
```

说明：

- `order` 越小越靠前（用于首页排序）。
- `tags` 不填时，会从该合集内文章的 tags 统计出出现频率最高的前 4 个作为合集卡片标签。

### 一个容易忽略的点：构建可能会“写回”Markdown

构建时会自动规范化 tags、补默认值；如果开启了 AI 摘要，还会把生成的 `description` 写回到 Markdown。

</details>

<details>
<summary>仓库状态面板（图表/炫技）</summary>

<!-- 这些都是图片（非可点击链接） -->

![作者概览](https://github-readme-stats.vercel.app/api?username=ChenyuHeee&show_icons=true&include_all_commits=true&hide_rank=false)

![语言分布](https://github-readme-stats.vercel.app/api/top-langs/?username=ChenyuHeee&layout=compact)

![连续贡献](https://streak-stats.demolab.com?user=ChenyuHeee)

![活跃度曲线](https://github-readme-activity-graph.vercel.app/graph?username=ChenyuHeee&area=true)

![仓库卡片](https://github-readme-stats.vercel.app/api/pin/?username=ChenyuHeee&repo=AutoBlog&show_owner=true)

![Star 趋势](https://api.star-history.com/svg?repos=ChenyuHeee/AutoBlog&type=Date)

![贡献者](https://contrib.rocks/image?repo=ChenyuHeee/AutoBlog)

</details>

<details>
<summary>工具脚本（偏开发/维护）</summary>

- `scripts/package_project.py`：将项目拷贝到 `dist/`（可加 `--zip` 打包）。
- `scripts/publish_open_source.py`：发布“脱敏 + 单提交历史”的快照分支到远程。

</details>

## 许可证

MIT
