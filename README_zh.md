# AutoBlog 静态站点生成器

AutoBlog 是一个使用 Python 编写的轻量级静态博客生成器，会将 `source/` 目录中的 Markdown 文章编译为 `public/` 下的可部署网站，以便直接托管在 GitHub Pages。

## 功能亮点

- 目录级 `_meta.yaml` 文件可为文件夹内文章自动追加标签与默认元数据。
- `collection` 配置可将整篇目录折叠为首页合集卡片，并生成专属聚合页面。
- 可选 AI 摘要：当 Markdown 未提供 `description` 时，可调用 DeepSeek API 自动补全摘要并写回文件。

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
python3 build.py
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

- `title`（推荐）：若缺失则使用 Markdown 中的首个 `#` 标题
- `date`（推荐）：若缺失则回退为文件的修改日期（`YYYY-MM-DD`）
- `slug`（选填）：若为空则默认使用文件名
- `description`（选填）：文章摘要，用于 meta 与首页列表
- `excerpt`（选填）：用于卡片/订阅摘要，不填则自动截取正文
- `tags`（选填）：标签列表，可写成数组或英文逗号分隔字符串
- `draft`（选填布尔值）：是否为草稿，默认 `false`
- `pinned`（选填）：将文章置顶到首页头图区域，可写布尔值或 `true`、`yes` 等字符串
- `pinned_priority`（选填数字）：多篇文章置顶时，数字越小越靠前；置顶文章默认优先级为 `0`

构建完成后，文章会输出到 `public/posts/{slug}/index.html`。

### 使用 `_meta.yaml` 管理文件夹元数据

`source/posts/` 下的任意目录都可以新增 `_meta.yaml`。该文件中的配置会自顶向下级联到同级及所有子目录中的 Markdown 文件，常用于批量添加标签或为某个系列设定默认字段。

```
source/posts/
  _meta.yaml
  ai/
    _meta.yaml
    intro.md
    tips.md
  travel/
    2025/
      diary.md
```

示例 `source/posts/ai/_meta.yaml`：

```yaml
tags: [AI, Machine Learning]
pinned: false
```

级联规则：

- `tags` 会与文章自身的标签合并并去重，文章级标签优先保留顺序；合并结果会写回 Front Matter，确保下次构建保持一致。
- 其它字段作为默认值，仅在文章缺少该字段时填充，允许在具体文章中覆盖。
- 多层目录的 `_meta.yaml` 会按照从根目录到当前目录的顺序依次叠加，可以逐层追加标签或覆盖默认值。

更新或新增 `_meta.yaml` 后执行 `python3 build.py`，构建脚本会在渲染前同步 Front Matter 并生成站点。

#### 将文件夹折叠为合集页面

在 `_meta.yaml` 中设置 `collection` 键，可以让该目录下的文章在首页中折叠为一张合集卡片。访客点击卡片会打开自动生成的合集列表页面，而归档、标签、搜索等功能仍会显示其中所有文章。

快速示例：

```yaml
collection: true
```

完整配置示例：

```yaml
collection:
  enabled: true
  title: "AI 学习笔记"
  description: "机器学习与大模型的实践记录。"
  order: 10            # 可选，数字越小越靠前
  tags: [AI, Machine Learning]
```

- `enabled`（默认 `true`）：用于在子目录中关闭或重新开启合集模式。
- `title` / `description`：自定义首页卡片与合集页面文案；留空时默认使用文件夹名称与自动生成的简介。
- `order`（整数，可选）：控制合集在首页的排序权重。未设置时按照合集内最新文章的日期排序。
- `tags`：决定合集卡片展示的标签列表；留空时系统会取合集文章中出现频率最高的前四个标签。

合集页面路径为 `posts/<folder>/`（例如 `public/posts/ai/index.html`），目录下的文章仍保持各自原有的访问 URL。

### 让文章置顶展示

1. 在文章 Front Matter 中加入 `pinned: true`（也接受 `1`、`yes` 等真值）。
2. （可选）设置 `pinned_priority` 来调整置顶顺序。数字越小优先级越高；不填写时置顶文章默认使用 `0`。
3. 运行 `python3 build.py`。优先级最高的置顶文章会出现在首页 Hero 区域，其余置顶文章会排在列表前端。
4. 当不再需要置顶时，删除或将 `pinned` 改为 `false` 即可。

## 静态页面

将 Markdown 文件放在 `source/pages/` 中即可生成独立页面（使用 `page.html` 模板）。除与文章共享的元数据外，还支持：

- `nav`（布尔值，默认 `true`）：是否展示在导航菜单。
- `nav_order`（数字，默认 `100`）：控制导航排序，数字越小越靠前。

示例（`source/pages/about.md`）：

```
---
title: 关于
slug: about
nav: true
nav_order: 20
---

自定义内容。
```

### About 页面设置步骤

1. 在 `source/pages/` 目录下创建或编辑 `about.md`，让 About 页面与其他独立页面一同管理。
2. 复制上方 Front Matter，并根据需要调整 `title`（导航标题）、`slug`（访问路径）或 `nav_order`（导航排序）。
3. 在 Front Matter 之后使用常规 Markdown 撰写个人简介，可插入标题、列表、图片或代码块。
4. 运行 `python3 build.py`，然后打开 `public/about/index.html`（或启动本地服务器）检查效果。后续更新内容时只需修改 Markdown 并重新构建即可。

## 标签与归档

当文章提供 `tags` 元数据时，构建流程会自动生成：

- `public/tags/index.html`：全部标签及使用次数。
- `public/tags/<tag>/index.html`：单个标签的文章归档。
- `public/archive/index.html`：年度归档列表。

## 搜索功能

构建流程会自动输出精简的 `public/search.json` 与 `public/search/index.html`。读者可通过
导航栏中的“Search”进入搜索页面，实时过滤全站文章与页面。索引会在每次构建时根据
最新内容更新，无需额外配置。

## 订阅与 SEO 辅助

配置 `site_url` 后会额外输出：

- `public/feed.xml`：RSS 订阅源。
- `public/sitemap.xml`：Sitemap，覆盖文章、标签、页面与归档。

模板也会自动注入 canonical、Open Graph、Twitter Summary 等元数据。

### 开启 RSS 订阅

1. 编辑 `source/config.yaml`，将 `site_url` 设置为站点的真实域名（如 `https://blog.example.com/`）。必须包含协议与末尾的 `/`，生成的 feed 才能提供绝对链接。
2. 再次运行 `python3 build.py`。构建完成后会在 `public/feed.xml` 写出 RSS，并自动在页面 `<head>` 中注入 `<link rel="alternate" type="application/rss+xml">`。
3. 将生成的静态文件部署上线。读者和聚合器即可通过 `<site_url>feed.xml`（示例：`https://blog.example.com/feed.xml`）订阅；你也可以把该链接添加到导航或侧栏。
4. 将订阅地址分享给读者，或提交到 Feedly、NetNewsWire 等阅读器。后续每次构建都会自动刷新订阅内容。

若希望完全关闭 RSS，在 `source/config.yaml` 中设置 `rss_enabled: false` 即可。即使脚本能够根据仓库推断 `site_url`，构建过程也会跳过 `feed.xml` 并在页面中移除相关链接。

## 自定义主题

- 修改 `templates/` 中的模板即可定制 HTML 结构。
- 站点全局样式位于 `source/assets/style.css`，可自由调整。

## 背景音乐播放器

在 `source/config.yaml` 中配置 `background_music` 块即可启用页面右下角的悬浮播放器：

```
background_music:
  enabled: true
  src: media/ambient.mp3
  title: "Calm Breeze"
  artist: "Lo-Fi Collective"
  cover: media/cover.jpg
  autoplay: true
  start_muted: true
```

使用提示：

1. 将音频文件放入 `source/assets/`（例如 `source/assets/media/ambient.mp3`）。构建时会按原有的相对路径复制到 `public/`，因此配置中无需写 `assets/` 前缀，直接使用 `media/ambient.mp3` 即可。
2. （可选）通过 `cover` 提供自定义封面，路径写法与音频相同（如 `media/cover.jpg`），若留空则显示默认图标。
3. 设置 `title` 与 `artist` 填充播放器内的曲目信息。
4. 如需自动播放可设置 `autoplay: true`。多数浏览器要求静音自动播放，建议同时开启 `start_muted: true`。若浏览器仍阻止自动播放，播放器会给出提示并等待用户交互。

当 `enabled` 为真且 `src` 指向有效文件时，播放器会自动注入到所有页面。访客可以播放/暂停、静音/取消静音并拖动进度条；方向键与 Home/End 也支持精确快进，满足可访问性需求。


## 深度集成的 AI 摘要（DeepSeek）

如果文章或页面没有在 Front Matter 中填写 `description`，AutoBlog 可以调用 DeepSeek Chat Completions API 自动生成摘要，并将结果写回 Markdown 文件。

1. 到 DeepSeek 平台申请 API Key，并将其写入 `source/config.yaml` 或设置环境变量 `DEEPSEEK_API_KEY`：

   ```yaml
   ai_summary:
     provider: deepseek
     api_key: "sk-你的密钥"
     model: deepseek-chat
     endpoint: https://api.deepseek.com/v1/chat/completions
     temperature: 0.2
     max_input_chars: 6000
     max_tokens: 200
    max_output_chars: 120
   ```

2. 如果还未更新依赖，请执行 `pip install -r requirements.txt`（新增了 `requests` 库用于发起 HTTP 调用）。
3. 运行 `python3 build.py`。构建过程中会提示“AI 摘要功能已启用”，脚本会为缺少 `description` 的 Markdown 调用 DeepSeek 生成约 50~110 字的中文摘要，并写回 Front Matter 供后续渲染。若调用失败或没有配置密钥，则继续使用内置的文本截取策略。

## GitHub Pages 配置

部署前先调整 `source/config.yaml`，示例如下：

```
github_repo: your-user/your-repo
github_branch: gh-pages
github_remote: origin
# github_remote_url: https://github.com/your-user/your-repo.git
# base_url: /your-repo/
# site_url: https://your-user.github.io/your-repo/
author: Your Name
# nav_links:
#   - label: 首页
#     url: /
#   - label: 标签
#     url: /tags/
```

- `github_repo` 用于推送提示，并自动推导默认的 `base_url`。推荐填写 `owner/repo` 形式；若仓库是 `your-user.github.io` 这类用户主页，可保持 `base_url` 为空以使用 `/`。
- `github_branch` 指向承载静态文件的分支，常见的选项有 `gh-pages` 或 `main`。
- `github_remote` 为已配置的 Git 远程名称（默认 `origin`）。
- `github_remote_url`（可选）用于显式指定推送地址，当本地未配置远程或需要自定义连接方式时使用。
- `base_url`（可选）用于覆盖推导出的公共路径。项目页通常设置为 `/<repo>/`，自定义域名可填完整 URL（如 `https://blog.example.com/`）。
- `site_url`（推荐）提供站点的绝对地址，以启用 RSS 与站点地图。
- `rss_enabled`（可选）控制是否输出 RSS。设为 `false` 可以停用订阅功能，同时保留 canonical 等元数据。
- `contacts`（可选）用于在首页侧栏展示联系方式，数组元素需包含 `label`、`url`，可选 `icon`（支持 `mail`、`github`、`linkedin`、`wechat` 等）与 `note` 文本。
- `author` 用于填充页面元数据。
- `nav_links`（可选）允许完全自定义导航栏；若不配置，会根据首页、归档、标签与 `nav: true` 页面自动生成。

## 自动推送部署

脚本可以在构建完成后自动将 `public/` 目录推送到 `config.yaml` 指定的分支：

```bash
python3 build.py --deploy
```

常用参数：

- `--dry-run`：执行全部步骤但跳过最终的 `git push`。
- `--remote`：覆盖 `config.yaml` 中的远程名称。
- `--branch`：覆盖目标分支。
- `--message`：自定义部署提交消息。

命令会把 `public/` 内容复制到临时仓库，生成一次提交并强制推送到目标分支。

## 部署到 GitHub Pages

1. 运行 `python3 build.py --deploy`（或先 `python3 build.py` 后自行处理推送）构建并推送静态资源。
2. 在仓库设置中启用 GitHub Pages，选择 `config.yaml` 中 `github_branch` 指定的分支，并将发布目录设置为仓库根目录。

GitHub Pages 会自动发布 `public/` 内的静态文件，几分钟内即可访问你的博客。祝创作愉快！
