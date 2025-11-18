# AutoBlog Static Site Generator

AutoBlog is a tiny static site generator written in Python. It converts Markdown posts stored in the `source/` directory into a publish-ready static site in `public/`, which can be deployed on GitHub Pages.

## Features

- YAML front matter support for per-post metadata such as title, date, slug, and description.
- Markdown-to-HTML rendering with fenced code blocks and tables.
- Jinja2 templates for flexible theming.
- Automatic index page generation ordered by publish date.
- Static asset copying from `source/assets/` to `public/`.

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
python build.py
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

- `title` (required)
- `date` (required) in ISO format `YYYY-MM-DD`
- `slug` (optional)
- `description` (optional) used in meta tags and the index page
- `draft` (optional boolean) defaults to `false`

## Customizing The Theme

Templates live in `templates/`. Update them or add new ones to tailor the site's appearance. Global styles can be adjusted in `source/assets/style.css`.

## GitHub Pages Configuration

Update `source/config.yaml` to match your repository before deploying:

```
github_repo: your-user/your-repo
github_branch: gh-pages
# base_url: /your-repo/
```

- `github_repo` is used for deployment hints and to infer the default `base_url` path. Use the `owner/repo` form. If you are publishing a user/organization site such as `your-user.github.io`, leave `base_url` unset so it remains `/`.
- `github_branch` is the branch that will host the generated files. Common choices are `gh-pages` or `main`.
- `base_url` (optional) overrides the inferred public path. Set it to `/<repo>/` for project pages or a full URL such as `https://blog.example.com/` when using a custom domain.

## Deploying to GitHub Pages

1. Run `python build.py` to produce fresh output in `public/`.
2. Commit and push the repository to GitHub.
3. In the repository settings, configure GitHub Pages to serve from the branch you set in `github_branch` and the `/public` folder (or configure an action/workflow that publishes that directory).

GitHub Pages will automatically serve the static files generated in `public/`.
