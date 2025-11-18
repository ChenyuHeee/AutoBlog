# AutoBlog 静态站点生成器

AutoBlog 是一个使用 Python 编写的轻量级静态博客生成器，会将 `source/` 目录中的 Markdown 文章编译为 `public/` 下的可部署网站，以便直接托管在 GitHub Pages。

## 功能亮点

- 支持 YAML Front Matter，可为文章配置标题、日期、摘要、描述、草稿等元数据。
- 使用 Markdown 库转换内容，内建代码高亮与表格支持。
- 基于 Jinja2 模板系统，便于自定义站点样式与布局。
- 自动生成按发布日期倒序排序的首页列表。
- 自动复制 `source/assets/` 中的静态资源（CSS、图片等）。

## 目录结构

```
source/
  posts/        # Markdown 文章（含 YAML Front Matter）
  assets/       # 静态资源文件，会原样复制
templates/      # Jinja2 模板文件
public/         # 构建输出目录（可删除，构建时会重建）
build.py        # 静态站点构建脚本
requirements.txt
```

## 环境要求

- Python 3.10 或更新版本（开发测试于 macOS，其他系统同样兼容）

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 快速构建

```bash
python build.py
```

该命令会清空并重新生成 `public/` 目录，终端会列出生成的文件。随后即可将整个仓库推送至 GitHub，并把 GitHub Pages 的发布目录指向 `public/`。

### 可选参数

- `--skip-clean`：构建时不删除现有的 `public/` 目录，适合增量更新。
- `--drafts`：包含标记为草稿（`draft: true`）的文章，默认跳过草稿。

## 撰写文章

在 `source/posts/` 下新增 Markdown 文件，格式示例：

```
---
title: "我的第一篇文章"
date: 2025-01-01
slug: my-first-post
description: "对博客的简短介绍。"
draft: false
---

Markdown 正文内容写在这里。
```

字段说明：

- `title`（必填）：文章标题
- `date`（必填）：发布日期，格式 `YYYY-MM-DD`
- `slug`（选填）：若为空则默认使用文件名
- `description`（选填）：文章摘要，用于 meta 与首页列表
- `draft`（选填布尔值）：是否为草稿，默认 `false`

构建完成后，文章会输出到 `public/posts/{slug}/index.html`。

## 自定义主题


## GitHub Pages 配置

部署前先调整 `source/config.yaml`，示例如下：

```
github_repo: your-user/your-repo
github_branch: gh-pages
# base_url: /your-repo/
```

- `github_repo` 用于推送提示，并自动推导默认的 `base_url`。推荐填写 `owner/repo` 形式；若仓库是 `your-user.github.io` 这类用户主页，可保持 `base_url` 为空以使用 `/`。
- `github_branch` 指向承载静态文件的分支，常见的选项有 `gh-pages` 或 `main`。
- `base_url`（可选）用于覆盖推导出的公共路径。项目页通常设置为 `/<repo>/`，自定义域名可填完整 URL（如 `https://blog.example.com/`）。

## 部署到 GitHub Pages

1. 运行 `python build.py` 生成最新的 `public/`。
2. 将代码提交并推送到 GitHub。
3. 在仓库设置中启用 GitHub Pages，选择 `config.yaml` 中 `github_branch` 指定的分支，并将目录设置为 `/public`；或配置自动化流程发布该目录。

GitHub Pages 会自动发布 `public/` 内的静态文件，几分钟内即可访问你的博客。祝创作愉快！
