#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "source"
PUBLIC_DIR = ROOT / "public"
TEMPLATES_DIR = ROOT / "templates"


@dataclass
class Post:
    title: str
    date: dt.date
    slug: str
    description: str
    content_markdown: str
    content_html: str
    draft: bool
    source_path: Path
    output_path: Path
    base_url: str

    @property
    def url(self) -> str:
        return join_url(self.base_url, "posts", self.slug, trailing_slash=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AutoBlog static site")
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Do not delete the public/ directory before writing new files",
    )
    parser.add_argument(
        "--drafts",
        action="store_true",
        help="Include posts where draft: true in the output",
    )
    return parser.parse_args()


def load_site_config(source_dir: Path) -> Dict[str, Any]:
    config_path = source_dir / "config.yaml"
    defaults: Dict[str, Any] = {
        "title": "My Blog",
        "description": "Thoughts, stories, and ideas.",
        "timezone": "UTC",
        "base_url": "/",
        "github_repo": "",
        "github_branch": "gh-pages",
    }
    if not config_path.exists():
        defaults["base_url"] = normalize_base_url(defaults["base_url"])
        return defaults
    with config_path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    merged = defaults.copy()
    merged.update(loaded)
    merged["github_repo"] = (merged.get("github_repo") or "").strip()
    merged["github_branch"] = merged.get("github_branch") or defaults["github_branch"]
    raw_base_url = loaded.get("base_url")
    if raw_base_url not in (None, ""):
        merged["base_url"] = normalize_base_url(raw_base_url)
    else:
        merged["base_url"] = normalize_base_url(infer_base_url(merged))
    return merged


def normalize_base_url(raw: Any) -> str:
    if not raw:
        return "/"
    if not isinstance(raw, str):
        raise TypeError("base_url must be a string")
    value = raw.strip()
    if not value:
        return "/"
    if value.startswith("http://") or value.startswith("https://"):
        return value if value.endswith("/") else value + "/"
    if not value.startswith("/"):
        value = "/" + value
    if not value.endswith("/"):
        value += "/"
    return value


def infer_base_url(config: Dict[str, Any]) -> str:
    repo = (config.get("github_repo") or "").strip()
    if not repo:
        return "/"
    repo_name = repo.split("/")[-1]
    if repo_name.endswith(".github.io"):
        return "/"
    return f"/{repo_name}/"


def join_url(base_url: str, *segments: str, trailing_slash: bool = False) -> str:
    path_segments = [segment.strip("/") for segment in segments if segment]
    if base_url.startswith("http://") or base_url.startswith("https://"):
        root = base_url.rstrip("/")
        path = "/".join(path_segments)
        url = root if not path else f"{root}/{path}"
    else:
        root = "" if base_url == "/" else base_url.rstrip("/")
        path = "/".join(path_segments)
        if not path:
            url = root or "/"
        elif root:
            url = f"{root}/{path}"
        else:
            url = f"/{path}"
    if trailing_slash and not url.endswith("/"):
        url += "/"
    return url


def make_url_builder(base_url: str):
    def builder(*segments: str, trailing_slash: bool = False) -> str:
        return join_url(base_url, *segments, trailing_slash=trailing_slash)

    return builder


def extract_front_matter(raw_text: str) -> Tuple[Dict[str, Any], str]:
    if not raw_text.lstrip().startswith("---"):
        return {}, raw_text
    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw_text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            front = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1 :])
            data = yaml.safe_load(front) or {}
            return data, body
    return {}, raw_text


def parse_date(value: Any) -> dt.date:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, dt.datetime):
        return value.date()
    if not isinstance(value, str):
        raise ValueError("date must be a string in YYYY-MM-DD format")
    return dt.date.fromisoformat(value)


def render_markdown(raw_markdown: str) -> str:
    md = markdown.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "codehilite",
            "toc",
            "sane_lists",
        ]
    )
    return md.convert(raw_markdown)


def summarize(description: str, html_content: str) -> str:
    if description:
        return description
    text: List[str] = []
    buffer = []
    inside_tag = False
    for char in html_content:
        if char == "<":
            inside_tag = True
            if buffer:
                text.append("".join(buffer).strip())
                buffer.clear()
            continue
        if char == ">":
            inside_tag = False
            continue
        if inside_tag:
            continue
        buffer.append(char)
    if buffer:
        text.append("".join(buffer).strip())
    joined = " ".join(segment for segment in text if segment)
    return joined[:197] + "..." if len(joined) > 200 else joined


def discover_posts(source_dir: Path, include_drafts: bool, base_url: str) -> List[Post]:
    posts_dir = source_dir / "posts"
    if not posts_dir.exists():
        return []
    posts: List[Post] = []
    for md_path in sorted(posts_dir.glob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        front_matter, body = extract_front_matter(raw)
        title = front_matter.get("title")
        if not title:
            raise ValueError(f"Missing title in {md_path}")
        date = parse_date(front_matter.get("date"))
        slug = front_matter.get("slug") or md_path.stem
        draft = bool(front_matter.get("draft", False))
        if draft and not include_drafts:
            continue
        html = render_markdown(body)
        description = summarize(front_matter.get("description", ""), html)
        output_path = PUBLIC_DIR / "posts" / slug / "index.html"
        posts.append(
            Post(
                title=title,
                date=date,
                slug=slug,
                description=description,
                content_markdown=body,
                content_html=html,
                draft=draft,
                source_path=md_path,
                output_path=output_path,
                base_url=base_url,
            )
        )
    posts.sort(key=lambda post: post.date, reverse=True)
    return posts


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def copy_assets(source_dir: Path, public_dir: Path) -> List[Path]:
    assets_dir = source_dir / "assets"
    copied: List[Path] = []
    if not assets_dir.exists():
        return copied
    for path in assets_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(assets_dir)
        target = public_dir / rel
        ensure_dirs(target)
        shutil.copy2(path, target)
        copied.append(target)
    return copied


def build_site(args: argparse.Namespace) -> None:
    if not args.skip_clean and PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    config = load_site_config(SOURCE_DIR)
    base_url = config.get("base_url", "/")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["site"] = config
    env.globals["build_time"] = dt.datetime.now(dt.timezone.utc)
    env.globals["base_url"] = base_url
    env.globals["url_for"] = make_url_builder(base_url)

    posts = discover_posts(SOURCE_DIR, include_drafts=args.drafts, base_url=base_url)

    index_template = env.get_template("index.html")
    post_template = env.get_template("post.html")

    rendered_files: List[Path] = []

    for post in posts:
        ensure_dirs(post.output_path)
        html = post_template.render(
            post=post,
            site=config,
            page_title=post.title,
            page_description=post.description,
        )
        post.output_path.write_text(html, encoding="utf-8")
        rendered_files.append(post.output_path)

    index_html = index_template.render(
        posts=posts,
        site=config,
        page_title=None,
        page_description=config.get("description", ""),
    )
    index_path = PUBLIC_DIR / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    rendered_files.append(index_path)

    assets = copy_assets(SOURCE_DIR, PUBLIC_DIR)
    rendered_files.extend(assets)

    print("Wrote:")
    for path in rendered_files:
        print(f"  {path.relative_to(ROOT)}")

    repo = config.get("github_repo")
    branch = config.get("github_branch")
    if repo and branch:
        print("\nGitHub Pages deployment tips:")
        print(f"  Remote repository : {repo}")
        print(f"  Target branch     : {branch}")
        print("  Suggested command : git subtree push --prefix public origin " + branch)


def main() -> None:
    args = parse_args()
    build_site(args)


if __name__ == "__main__":
    main()
