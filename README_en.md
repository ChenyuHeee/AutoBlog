<div align="center">

# AutoBlog

A lightweight static blog generator written in Python: build Markdown in `source/` into a deployable site under `public/`, ready for GitHub Pages.

<!-- Repo: ChenyuHeee/AutoBlog -->

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

[![README ZH](https://img.shields.io/badge/README-%E4%B8%AD%E6%96%87-1f6feb?style=for-the-badge)](README.md)
[![README EN](https://img.shields.io/badge/README-English-1f6feb?style=for-the-badge)](README_en.md)

</div>

**Quick links**

- [5-minute quickstart](#quickstart)
- [Desktop App (edit/preview/build/deploy)](#desktop-app)
- [Advanced config (config.yaml)](#advanced-config)
- [Contributing](#contributing)

## What is this? (For anyone who wants a blog)

AutoBlog turns your Markdown posts into a complete static blog site, and lets you deploy to GitHub Pages with a single command.

You get:

- Post pages + a homepage list
- Tags, archives, and site search
- RSS + sitemap (auto-generated once you set `site_url`)

You only do: write Markdown, run build/deploy.

<a name="quickstart"></a>

## 5-minute Quickstart: from zero to live

### 0) Prerequisites

- Python 3.10+
- Git installed locally
- A GitHub repository (to host your blog)

### 1) Clone

```bash
git clone https://github.com/ChenyuHeee/AutoBlog
cd AutoBlog
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell) equivalent:

```powershell
git clone https://github.com/ChenyuHeee/AutoBlog
cd AutoBlog
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

<a name="desktop-app"></a>

### 2) Recommended: use the Desktop App (edit + preview + build + deploy)

If you don’t want to edit YAML / run commands manually, use the Desktop App to:

- Edit `source/config.yaml` in a preferences UI
- Edit Markdown with live preview
- Edit theme files
- Click Build / Preview / Deploy

Install dependencies:

```bash
pip install -r requirements.txt -r requirements_desktop.txt
```

Run:

```bash
python run_desktop.py
```

Notes:

- “Deploy” defaults to dry-run (no push). If you disable dry-run, it will `git push --force` to your Pages branch.

### 3) Create your site config

Copy the example config to the real config:

```bash
cp source/config.yaml.example.yaml source/config.yaml
```

Windows (PowerShell) equivalent:

```powershell
Copy-Item source\config.yaml.example.yaml source\config.yaml
```

Edit `source/config.yaml` (minimal example):

```yaml
nav_links:
  - label: Home
    url: /
  - label: Tags
    url: /tags/
  - label: GitHub
    url: https://github.com/YourName/YourRepo

contacts:
  - label: Email: you@example.com
    url: mailto:you@example.com
    icon: mail
  - label: GitHub @YourName
    url: https://github.com/YourName
    icon: github

github_repo: your-user/your-repo
github_branch: gh-pages
github_remote: origin

# Key: base_url controls the GitHub Pages path
# 1) If this is a “project page” (https://your-user.github.io/your-repo/):
base_url: /your-repo/
# 2) If this is a “user/organization page” (https://your-user.github.io/):
# base_url: /

# Recommended: set the absolute site URL so RSS/sitemap links are absolute
# site_url: https://your-user.github.io/your-repo/
```

### 4) Write your first post

Create a Markdown file under `source/posts/`, for example:

```markdown
---
title: "Hello AutoBlog"
date: 2025-12-29
slug: hello
description: "My first blog post."
---

Write your content here.
```

### 5) Preview locally

```bash
python3 build.py
```

Open `public/index.html` in your browser.

### 6) Deploy to GitHub Pages

```bash
python3 build.py --deploy
```

Then enable GitHub Pages in your repo settings:

- Source: choose `github_branch` (the example uses `gh-pages`)
- Folder: select the repository root (root)

After a few minutes, your site will be accessible via your Pages URL.

## Common gotchas (the top 2)

1. Wrong path / 404 assets: check `base_url` first (for project pages it’s usually `/<repo>/`).
2. Wrong links in RSS/sitemap: set `site_url` (must include `https://` and end with `/`).

## More features (optional)

- Folder metadata: `source/posts/**/_meta.yaml` can batch-apply tags / default fields
- Collections: collapse a directory into a single homepage collection card
- AI summaries: generate `description` via DeepSeek and write back

<a name="advanced-config"></a>

<details>
<summary>Advanced configuration (config.yaml reference)</summary>

Authoritative reference: `source/config.yaml.example.yaml` (copy it to `source/config.yaml` and edit).

### URL / GitHub Pages

- `github_repo`: `owner/repo`, used to infer Pages URL and push target
- `github_branch`: the branch that hosts static files (commonly `gh-pages`)
- `github_remote`: local git remote name (default: `origin`)
- `github_remote_url`: explicit push URL (use this if you don’t want to rely on local remotes or `github_repo`)
- `base_url`: URL prefix (project pages usually `/<repo>/`; user/org pages usually `/`)
- `site_url`: absolute site URL (for absolute RSS/sitemap links; must start with `https://` and end with `/`)

### Navbar (optional, fully custom)

If not configured, AutoBlog generates a default nav automatically. To fully customize:

```yaml
nav_links:
  - label: Home
    url: /
  - label: Tags
    url: /tags/
  - label: GitHub
    url: https://github.com/ChenyuHeee/AutoBlog
```

### RSS / Sitemap

- `rss_enabled: false`: disable RSS output

### Sidebar contacts

```yaml
contacts:
  - label: Email: you@example.com
    url: mailto:you@example.com
    icon: mail
    note: Feel free to reach out
  - label: GitHub @YourName
    url: https://github.com/YourName
    icon: github
```

### Background music player

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

`src/cover` are paths relative to `source/assets/` (e.g. put the file at `source/assets/media/your.mp3`, then use `media/your.mp3`).

### AI summaries (DeepSeek)

If a post/page has no `description`, AutoBlog can generate one and write it back.

```yaml
ai_summary:
  provider: deepseek
  api_key: ""  # recommended: set via DEEPSEEK_API_KEY env var
  model: deepseek-chat
  endpoint: https://api.deepseek.com/v1/chat/completions
  temperature: 0.2
  max_input_chars: 6000
  max_tokens: 200
  max_output_chars: 120
```

</details>

<details>
<summary>Advanced writing (Front Matter / _meta.yaml / collections / pinning)</summary>

### Post Front Matter

Posts (`source/posts/**/*.md`) support YAML front matter, for example:

```yaml
---
title: "My first post"
date: 2025-12-29
slug: my-first-post
description: "One-line summary (used for cards/SEO)."
excerpt: "Optional: shorter summary for lists/RSS."
tags: [AIOps, Papers]
draft: false

# Pinning (both forms are supported):
pinned: true
# or pinned: 10  (numbers are treated as pinned and can act as a priority hint)
pinned_priority: 0
---
```

Notes:

- `tags` can be a YAML list, or a string (comma/semicolon/slash separated).
- `draft: true` is excluded by default (use `python3 build.py --drafts` to include drafts).
- `pinned: true` pins a post; smaller `pinned_priority` comes first; default is `0` when pinned.

### Folder-level `_meta.yaml` (defaults + tags)

Put `_meta.yaml` under any folder inside `source/posts/`. It applies to that folder and all subfolders, and merges along the directory chain:

```text
source/posts/
  _meta.yaml
  aiops/
    _meta.yaml
    intro.md
```

It supports two key behaviors:

1) `tags`: merged with per-post `tags`, deduplicated (case-insensitive), and the merged result is written back into the post’s front matter.

2) Other keys: treated as defaults and only filled when the post is missing that field (may also be written back).

Example:

```yaml
tags: [AIOps]
draft: false
```

### Collections

Configure `collection` in `_meta.yaml` to collapse a directory into a single homepage collection card, and generate a collection listing page.

Minimal:

```yaml
collection: true
```

Full form (override title/description/order/tags):

```yaml
collection:
  enabled: true
  title: "AIOps Notes"
  description: "Paper reading, reproductions, and practice notes."
  order: 10
  tags: [AIOps, Papers]
```

Disable collections (e.g. for a subfolder):

```yaml
collection: false
# or
collection:
  enabled: false
```

Notes:

- Smaller `order` comes first (used for homepage sorting).
- If `tags` is omitted, AutoBlog chooses the top 4 most frequent tags within that collection.

### One important detail: the build may “write back” to Markdown

During build, AutoBlog can normalize tags and fill defaults; if AI summaries are enabled, it will also write generated `description` back into the Markdown.

</details>

<details>
<summary>Repo Status Dashboard</summary>

<!-- These are images (not clickable links). -->

![Owner Stats](https://github-readme-stats.vercel.app/api?username=ChenyuHeee&show_icons=true&include_all_commits=true&hide_rank=false)

![Top Languages](https://github-readme-stats.vercel.app/api/top-langs/?username=ChenyuHeee&layout=compact)

![Streak](https://streak-stats.demolab.com?user=ChenyuHeee)

![Activity Graph](https://github-readme-activity-graph.vercel.app/graph?username=ChenyuHeee&area=true)

![Repo Card](https://github-readme-stats.vercel.app/api/pin/?username=ChenyuHeee&repo=AutoBlog&show_owner=true)

![Star History](https://api.star-history.com/svg?repos=ChenyuHeee/AutoBlog&type=Date)

![Contributors](https://contrib.rocks/image?repo=ChenyuHeee/AutoBlog)

</details>

<details>
<summary>Tooling Scripts (dev/maintenance)</summary>

- `scripts/package_project.py`: copy the project into `dist/` (optionally `--zip`).
- `scripts/publish_open_source.py`: publish a sanitized, single-commit snapshot branch.

</details>

## License

MIT
