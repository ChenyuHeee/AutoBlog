# AutoBlog Static Site Generator

AutoBlog is a tiny static site generator written in Python. It converts Markdown posts stored in the `source/` directory into a publish-ready static site in `public/`, which can be deployed on GitHub Pages.

## Features

- YAML front matter support for per-post metadata such as title, date, slug, and description.
- Markdown-to-HTML rendering with fenced code blocks and tables.
- Jinja2 templates for flexible theming.
- Automatic index page generation ordered by publish date.
- Modern responsive layout with featured post, sidebar, and tag badges.
- Built-in tag index, per-tag archive pages, and yearly archive.
- Folder-level `_meta.yaml` files cascade tags and default metadata to nested posts.
- Optional collection folders that collapse whole directories into a single homepage card with a generated index page.
- Client-side search page powered by an automatically generated JSON index.
- Automatic newer/older navigation links and related-post suggestions on article pages.
- RSS feed (`public/feed.xml`) and XML sitemap (`public/sitemap.xml`) generation.
- Static asset copying from `source/assets/` to `public/`.
- Optional background music player with floating controls, progress, and mute/autoplay toggles.
- Optional AI summaries for posts or pages that are missing `description` metadata (DeepSeek API integration).

## Project Layout

```
source/
  posts/        # Markdown articles with YAML front matter
  assets/       # Static files copied as-is (CSS, images, etc.)
templates/      # Jinja2 templates used to render pages
public/         # Generated output (safe to delete; regenerated on build)
build.py        # Static site builder script
requirements.txt
```

## Prerequisites

- Python 3.10 or newer (tested on macOS but should work anywhere Python runs)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python3 build.py
```

The command removes any existing `public/` directory, regenerates the site, and reports which files were written. The generated site can then be pushed to GitHub and served via GitHub Pages by pointing Pages to the `public/` folder.

### Optional flags

- `--skip-clean`: keep the existing `public/` directory instead of deleting it before the build. This can make incremental builds faster when you only touch a few files.
- `--drafts`: include posts marked as drafts in the output. Drafts are excluded by default.

## Creating Posts

Create new Markdown files under `source/posts/` with YAML front matter:

```
---
title: "My First Post"
date: 2025-01-01
slug: my-first-post
description: "Quick intro to my blog."
draft: false
---

Markdown content goes here.
```

The `slug` controls the URL under `public/posts/{slug}/index.html`. If omitted, the file name is used. Supported metadata keys:

- `title` (recommended) — falls back to the first `#` heading if omitted
- `date` (recommended) in ISO format `YYYY-MM-DD` — defaults to the file's last modified date if missing
- `slug` (optional)
- `description` (optional) used in meta tags and the index page
- `excerpt` (optional) alternate summary used on cards and feeds
- `tags` (optional) list/array or comma-separated string e.g. `tags: [python, static-site]`
- `draft` (optional boolean) defaults to `false`
- `pinned` (optional) mark the post as featured on the homepage hero; accepts booleans or truthy strings like `true`
- `pinned_priority` (optional number) smaller numbers win when multiple posts are pinned; ties fall back to most recent date

### Folder Metadata with `_meta.yaml`

Every directory beneath `source/posts/` can include an optional `_meta.yaml` file. Its contents cascade to every Markdown file inside the same folder (and all nested subfolders). Typical use cases include tagging whole categories at once or defining shared defaults such as `draft: true` while drafting a series.

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

Example `source/posts/ai/_meta.yaml`:

```yaml
tags: [AI, Machine Learning]
pinned: false
```

How the builder treats folder metadata:

- `tags` are appended to each file's own tags (deduplicated, keeping the post-level order first). The merged tags are written back into the Markdown front matter so future builds stay in sync.
- Any other keys act as defaults. They only populate a post when the field is missing, letting individual files override the folder setting when needed.
- Metadata files stack from the top-level `source/posts/_meta.yaml` down to the current folder. Deeper folders can add more tags or override defaults established higher up.

Create or edit `_meta.yaml`, then run `python3 build.py`. The builder will update front matter as required before rendering the site.

#### Turning a Folder into a Collection

Set the `collection` key in `_meta.yaml` to hide individual articles from the homepage grid and expose them through a dedicated collection page instead. Readers will see a single card on the homepage; clicking it opens an automatically generated index for that folder, while archives, tag pages, and search continue to list every article as usual.

Minimal example:

```yaml
collection: true
```

Extended configuration:

```yaml
collection:
  enabled: true
  title: "AI 学习笔记"
  description: "机器学习与大模型的实践记录。"
  order: 10            # optional; smaller numbers appear earlier on the homepage
  tags: [AI, Machine Learning]
```

- `enabled` (default `true`) lets you toggle the behaviour per folder or re-enable it in nested directories.
- `title` / `description` override the card and collection page copy; omit them to fall back to the folder name and an auto-generated summary.
- `order` (integer) allows manual positioning among other homepage items. Collections without `order` fall back to date ordering based on the newest post inside.
- `tags` control which tag chips appear on the homepage card. Leave blank to let AutoBlog surface up to four of the most common tags from the collected posts.

Collections live at `posts/<folder>/` (for example `public/posts/ai/index.html`). All posts remain accessible via their original URLs.

### Featuring a Pinned Post

1. Add `pinned: true` to the post front matter. The builder treats any truthy value (such as `1` or `yes`) as pinned.
2. (Optional) Set `pinned_priority` to control the ordering when more than one post is pinned. Lower numbers appear first; leaving it blank defaults to `0` for pinned posts.
3. Run `python3 build.py`. The highest-priority pinned post becomes the homepage hero with the "Pinned Article" label, and remaining pinned posts flow into the grid ahead of regular posts.
4. Remove or set `pinned: false` when you no longer want the post highlighted.

## Static Pages

Markdown files placed in `source/pages/` become standalone pages rendered with the `page.html` template. Each page supports the same front matter fields as posts, plus:

- `nav` (boolean, default `true`) to control whether the page appears in the auto-generated navigation bar.
- `nav_order` (number, default `100`) to sort links when `nav` is enabled.

Example (`source/pages/about.md`):

```
---
title: About
slug: about
nav: true
nav_order: 20
---

Custom content here.
```

### About Page Walkthrough

1. Create `source/pages/about.md` (or edit the existing file) so the About page lives alongside other standalone pages.
2. Paste the front matter shown above, adjusting `title`, `slug`, or `nav_order` if you prefer a different label, URL path, or position in the header navigation.
3. Write your bio using regular Markdown underneath the front matter—headings, lists, images, and code blocks are all supported.
4. Run `python3 build.py` and open `public/about/index.html` (or start a local server) to confirm the layout. Update the copy anytime and rebuild to publish changes.

## Tags & Archives

Posts with the `tags` field automatically appear on:

- `public/tags/index.html` — tag directory with usage counts.
- `public/tags/<tag>/index.html` — per-tag archives.
- `public/archive/index.html` — posts grouped by year.

## Search

Every build writes a compact `public/search.json` index and renders `public/search/index.html`.
Readers can open the Search page from the header navigation to filter posts and pages instantly
without leaving the site. The index is regenerated from published content on each build, so no
extra configuration is required.

## Feeds & SEO Helpers

When `site_url` is configured, AutoBlog also writes:

- `public/feed.xml` — RSS 2.0 feed for the latest posts.
- `public/sitemap.xml` — XML sitemap covering posts, tags, pages, and archive.

Canonical URLs, Open Graph, and Twitter summary metadata are emitted from templates using the same `site_url` setting.

### Enabling RSS Subscriptions

1. Open `source/config.yaml` and set `site_url` to your canonical domain, e.g. `https://blog.example.com/`. The value must include the protocol and trailing slash so the feed exposes absolute links.
2. Re-run `python3 build.py`. The build writes `public/feed.xml` alongside the rest of the site and injects a `<link rel="alternate" type="application/rss+xml">` tag into every page.
3. Deploy the generated files. Visitors (or feed readers) can subscribe via `<site_url>feed.xml` (for example `https://blog.example.com/feed.xml`), and you can surface the feed URL in navigation or the sidebar if desired.
4. Share the feed link or add it to services such as Feedly/NetNewsWire. Future builds keep the feed fresh automatically.

To disable RSS entirely, set `rss_enabled: false` in `source/config.yaml`. The build skips `feed.xml` and omits RSS references from page templates even if a `site_url` can be inferred automatically.

## Customizing The Theme

Templates live in `templates/`. Update them or add new ones to tailor the site's appearance. Global styles can be adjusted in `source/assets/style.css`.

## Background Music Player

Enable the floating audio player with the `background_music` block in `source/config.yaml`:

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

How it works:

1. Place the audio file somewhere under `source/assets/` (for example `source/assets/media/ambient.mp3`). The generator copies it into `public/` using the same relative path, so reference it without the leading `assets/` prefix (e.g. `media/ambient.mp3`).
2. (Optional) Add a cover image path for a custom thumbnail using the same convention (`media/cover.jpg`). If omitted, the player shows a default icon.
3. Provide `title` and `artist` strings to populate the metadata row beneath the controls.
4. Set `autoplay: true` if you want playback to start automatically. Most browsers require muted autoplay, so pair this with `start_muted: true` to maximize the chance it succeeds. When autoplay is blocked the player surfaces a visual cue and waits for user interaction.

The player appears at the bottom-right of every page whenever `enabled` is truthy and `src` points to a valid asset. Visitors can play/pause, mute/unmute, and scrub through the track. The controls respond to keyboard input (arrow keys, Home/End) for accessibility.

## AI-Generated Summaries (DeepSeek)

AutoBlog can call DeepSeek's Chat Completions API to fill in `description` fields for Markdown files that don't provide one.

1. Obtain a DeepSeek API key and either set the `DEEPSEEK_API_KEY` environment variable or edit `source/config.yaml`:

   ```yaml
   ai_summary:
     provider: deepseek
     api_key: "sk-your-key"
     model: deepseek-chat
     endpoint: https://api.deepseek.com/v1/chat/completions
     temperature: 0.2
     max_input_chars: 6000
     max_tokens: 200
    max_output_chars: 120
   ```

2. Run `pip install -r requirements.txt` if you have not installed the updated dependencies (the feature relies on `requests`).
3. Rebuild the site via `python3 build.py`. When the key is present, the builder prints a notice, requests a concise (~50–110 Chinese characters) summary from DeepSeek for each Markdown file without a `description`, writes the generated text back into the file's front matter, and then continues rendering as usual.

If the API key is missing or a request fails, AutoBlog falls back to the built-in heuristic summarizer so builds remain deterministic.

## GitHub Pages Configuration

Update `source/config.yaml` to match your repository before deploying:

```
github_repo: your-user/your-repo
github_branch: gh-pages
github_remote: origin
# github_remote_url: https://github.com/your-user/your-repo.git
# base_url: /your-repo/
# site_url: https://your-user.github.io/your-repo/
author: Your Name
# nav_links:
#   - label: Home
#     url: /
#   - label: Tags
#     url: /tags/
```

- `github_repo` is used for deployment hints and to infer the default `base_url` path. Use the `owner/repo` form. If you are publishing a user/organization site such as `your-user.github.io`, leave `base_url` unset so it remains `/`.
- `github_branch` is the branch that will host the generated files. Common choices are `gh-pages` or `main`.
- `github_remote` is the Git remote that already points to your repository (defaults to `origin`).
- `github_remote_url` (optional) overrides the remote URL AutoBlog should push to. Leave it blank to reuse the URL configured for `github_remote`.
- `base_url` (optional) overrides the inferred public path. Set it to `/<repo>/` for project pages or a full URL such as `https://blog.example.com/` when using a custom domain.
- `site_url` (optional but recommended) sets the canonical absolute URL of your site and enables RSS/sitemap generation.
- `rss_enabled` (optional) toggles RSS feed generation. Set it to `false` to keep feeds disabled while still benefiting from canonical URLs and sitemaps.
- `contacts` (optional) lists contact methods rendered in the home sidebar. Each item should define `label`, `url`, and optionally `icon` (`mail`, `github`, `linkedin`, `wechat`, or leave blank) plus a short `note`.
- `author` populates document metadata.
- `nav_links` (optional) lets you explicitly define the header navigation. When omitted, the builder composes a menu from Home, Archive, Tags, and any pages with `nav: true`.

## Automated Deployment

AutoBlog can build and push the `public/` directory directly to the GitHub branch defined in your configuration.

```bash
python3 build.py --deploy
```

Useful flags:

- `--dry-run`: perform every step except the final `git push`.
- `--remote`: override the remote name from `config.yaml`.
- `--branch`: override the target branch from `config.yaml`.
- `--message`: provide a custom commit message for the deployment.

The deploy command copies the rendered `public/` directory into a temporary repository, commits the files, and force pushes the result to the configured branch.

## Deploying to GitHub Pages

1. Run `python3 build.py --deploy` to build and push the static files to the configured branch (or `python3 build.py` followed by your own deployment flow).
2. In the repository settings, configure GitHub Pages to serve from the branch you set in `github_branch` (typically at the repository root).

GitHub Pages will automatically serve the static files generated in `public/`.
