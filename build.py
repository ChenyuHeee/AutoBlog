#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import markdown
import requests
import yaml
from requests import RequestException
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "source"
PUBLIC_DIR = ROOT / "public"
TEMPLATES_DIR = ROOT / "templates"

HEADING_PATTERN = re.compile(r"^\s{0,3}#\s+(?P<title>.+)$", re.MULTILINE)

SUMMARY_BREAKPOINTS = ["。", "！", "？", ".", "!", "?"]

POST_FOLDER_META_FILENAME = "_meta.yaml"
COLLECTION_META_KEY = "collection"


def clamp_summary(text: str | None, limit: int = 200) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    snippet = cleaned[:limit].rstrip()
    best_break = -1
    for symbol in SUMMARY_BREAKPOINTS:
        index = snippet.rfind(symbol)
        if index > limit * 0.4 and index > best_break:
            best_break = index
    if best_break != -1:
        return snippet[: best_break + 1]
    return snippet + "…"


@dataclass
class Post:
    title: str
    date: dt.date
    slug: str
    slug_segments: List[str]
    group_segments: List[str]
    description: str
    content_markdown: str
    content_html: str
    draft: bool
    source_path: Path
    output_path: Path
    base_url: str
    tags: List[str]
    word_count: int
    reading_time_minutes: int
    pinned: bool
    pinned_priority: int
    collection_path: Optional[str] = None
    is_collection: bool = False

    @property
    def url(self) -> str:
        return join_url(self.base_url, "posts", *self.slug_segments, trailing_slash=True)

    @property
    def group_path(self) -> str:
        if not self.group_segments:
            return ""
        return "/".join(self.group_segments)

    @property
    def group_label(self) -> str:
        if not self.group_segments:
            return ""
        return self.group_segments[-1]

    @property
    def reading_time_label(self) -> str:
        return f"约 {self.reading_time_minutes} 分钟阅读"


@dataclass
class CollectionConfig:
    enabled: bool = True
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class CollectionState:
    config: Optional[CollectionConfig]
    anchor_path: Optional[Path]


@dataclass
class CollectionEntry:
    title: str
    description: str
    slug_segments: List[str]
    group_segments: List[str]
    base_url: str
    posts: List[Post]
    tags: List[str]
    order: Optional[int] = None
    collection_path: str = ""
    latest_date: Optional[dt.date] = None
    is_collection: bool = True
    pinned: bool = False

    @property
    def slug(self) -> str:
        return self.slug_segments[-1] if self.slug_segments else "collection"

    @property
    def url(self) -> str:
        return join_url(self.base_url, "posts", *self.slug_segments, trailing_slash=True)

    @property
    def date(self) -> dt.date:
        if self.latest_date:
            return self.latest_date
        return dt.date.today()

    @property
    def reading_time_label(self) -> str:
        return f"共 {self.post_count} 篇文章"

    @property
    def post_count(self) -> int:
        return len(self.posts)

    @property
    def group_path(self) -> str:
        if not self.group_segments:
            return ""
        return "/".join(self.group_segments)

    @property
    def group_label(self) -> str:
        if not self.group_segments:
            return ""
        return self.group_segments[-1]


@dataclass
class Page:
    title: str
    slug: str
    description: str
    content_markdown: str
    content_html: str
    source_path: Path
    output_path: Path
    base_url: str
    show_in_nav: bool
    nav_order: int

    @property
    def url(self) -> str:
        return join_url(self.base_url, self.slug, trailing_slash=True)


@dataclass
class TagInfo:
    name: str
    slug: str
    url: str
    posts: List[Post]

    @property
    def count(self) -> int:
        return len(self.posts)


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
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="After building, push the public/ directory to the configured GitHub branch",
    )
    parser.add_argument(
        "--remote",
        help="Override the Git remote name defined in config.yaml (default: github_remote)",
    )
    parser.add_argument(
        "--branch",
        help="Override the deployment branch defined in config.yaml (default: github_branch)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare the deployment but skip the final git push",
    )
    parser.add_argument(
        "--message",
        help="Custom commit message for the deployment push",
    )
    return parser.parse_args()


def load_site_config(source_dir: Path) -> Dict[str, Any]:
    config_path = source_dir / "config.yaml"
    defaults: Dict[str, Any] = {
        "title": "我的博客",
        "description": "记录我的想法、故事与灵感。",
        "timezone": "UTC",
        "base_url": "/",
        "github_repo": "",
        "github_branch": "gh-pages",
        "github_remote": "origin",
        "github_remote_url": "",
        "site_url": "",
        "author": "",
        "rss_enabled": True,
        "contacts": [],
        "background_music": {
            "enabled": False,
            "src": "",
            "title": "",
            "artist": "",
            "cover": "",
            "autoplay": False,
            "start_muted": False,
        },
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
    merged["github_remote"] = merged.get("github_remote") or defaults["github_remote"]
    merged["github_remote_url"] = (merged.get("github_remote_url") or "").strip()
    raw_base_url = loaded.get("base_url")
    if raw_base_url not in (None, ""):
        merged["base_url"] = normalize_base_url(raw_base_url)
    else:
        merged["base_url"] = normalize_base_url(infer_base_url(merged))
    merged["rss_enabled"] = coerce_bool(merged.get("rss_enabled"), True)

    raw_site_url = loaded.get("site_url")
    site_url = normalize_site_url(raw_site_url) if raw_site_url else ""
    if not site_url:
        inferred = infer_site_url(merged)
        site_url = normalize_site_url(inferred) if inferred else ""
    merged["site_url"] = site_url
    merged["contacts"] = normalize_contacts(loaded.get("contacts"))
    merged["background_music"] = normalize_background_music(loaded.get("background_music"))
    merged["ai_summary"] = normalize_ai_summary(loaded.get("ai_summary"))
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


def normalize_site_url(raw: Any) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise TypeError("site_url must be a string")
    value = raw.strip()
    if not value:
        return ""
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ValueError("site_url must start with http:// or https://")
    return value if value.endswith("/") else value + "/"


def infer_site_url(config: Dict[str, Any]) -> str:
    repo = (config.get("github_repo") or "").strip()
    if not repo or "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    if name.endswith(".github.io"):
        return f"https://{name}/"
    if owner:
        return f"https://{owner}.github.io/{name}/"
    return ""


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


def coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return default
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
        return default
    return default


def normalize_contacts(raw: Any) -> List[Dict[str, str]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not label or not url:
            continue
        icon = str(entry.get("icon", "")).strip().lower()
        note = str(entry.get("note", "")).strip()
        normalized.append({
            "label": label,
            "url": url,
            "icon": icon,
            "note": note,
        })
    return normalized


def normalize_background_music(raw: Any) -> Dict[str, Any]:
    defaults = {
        "enabled": False,
        "src": "",
        "title": "",
        "artist": "",
        "cover": "",
        "autoplay": False,
        "start_muted": False,
    }
    if raw in (None, ""):
        return defaults
    if isinstance(raw, str):
        value = raw.strip()
        if value:
            result = defaults.copy()
            result["src"] = value
            result["enabled"] = True
            return result
        return defaults
    if not isinstance(raw, dict):
        return defaults
    result = defaults.copy()
    for key in ("src", "title", "artist", "cover"):
        value = raw.get(key)
        if isinstance(value, str):
            result[key] = value.strip()
    result["autoplay"] = coerce_bool(raw.get("autoplay"), defaults["autoplay"])
    result["start_muted"] = coerce_bool(raw.get("start_muted"), defaults["start_muted"])
    result["enabled"] = bool(result["src"])
    return result


def normalize_ai_summary(raw: Any) -> Dict[str, Any]:
    defaults = {
        "provider": "deepseek",
        "api_key": "",
        "model": "deepseek-chat",
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "temperature": 0.2,
        "max_input_chars": 6000,
        "max_output_chars": 120,
        "max_tokens": 200,
        "timeout": 20,
        "max_retries": 2,
        "enabled": False,
    }
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not isinstance(raw, dict):
        raw = {} if raw else {}
    result = defaults.copy()
    for key in ("provider", "model", "endpoint"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    temperature_value = raw.get("temperature")
    if temperature_value is not None:
        try:
            result["temperature"] = float(temperature_value)
        except (TypeError, ValueError):
            pass
    for key in ("max_input_chars", "max_output_chars", "max_tokens", "timeout", "max_retries"):
        raw_value = raw.get(key)
        if raw_value is None:
            continue
        try:
            result[key] = int(float(raw_value))
        except (TypeError, ValueError):
            continue
    api_key = raw.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip()
    else:
        api_key = ""
    if not api_key and env_key:
        api_key = env_key
    result["api_key"] = api_key
    enabled_flag = raw.get("enabled")
    if enabled_flag is None:
        result["enabled"] = bool(api_key)
    else:
        result["enabled"] = bool(enabled_flag) and bool(api_key)
    return result


class LLMSummarizer:
    def __init__(self, settings: Dict[str, Any]):
        self.provider = settings.get("provider", "deepseek")
        self.api_key = settings.get("api_key", "")
        self.model = settings.get("model", "deepseek-chat")
        self.endpoint = settings.get("endpoint", "https://api.deepseek.com/v1/chat/completions")
        self.temperature = float(settings.get("temperature", 0.2))
        self.max_input_chars = int(settings.get("max_input_chars", 6000))
        self.max_output_chars = int(settings.get("max_output_chars", 120))
        self.max_tokens = int(settings.get("max_tokens", 200))
        self.timeout = int(settings.get("timeout", 20))
        self.max_retries = max(1, int(settings.get("max_retries", 2)))
        self.enabled = bool(settings.get("enabled", False)) and bool(self.api_key)
        if not self.api_key:
            self.enabled = False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Optional["LLMSummarizer"]:
        settings = config.get("ai_summary") or {}
        summarizer = cls(settings)
        return summarizer if summarizer.enabled else None

    def generate_summary(
        self,
        *,
        title: str,
        plain_text: str,
        tags: List[str],
        slug: str,
        item_type: str,
    ) -> Optional[str]:
        if not self.enabled:
            return None
        corpus = (plain_text or "").strip()
        if not corpus:
            return None
        truncated = corpus[: self.max_input_chars]
        tag_line = ", ".join(tags) if tags else "无标签"
        lower_bound = min(
            max(40, self.max_output_chars // 2),
            max(40, self.max_output_chars - 40),
        )
        if lower_bound >= self.max_output_chars:
            lower_bound = max(20, self.max_output_chars - 10)
        user_prompt = (
            "请基于以下{item_type}内容，撰写一段流畅的中文摘要，"
            "字数控制在约 {lower} 至 {limit} 个汉字，"
            "突出主题与读者收获，避免列表、Markdown 标记或额外说明。"
            "\n标题：{title}\n标签：{tags}\n正文：\n{content}"
        ).format(
            item_type="文章" if item_type == "post" else "页面",
            lower=lower_bound,
            limit=self.max_output_chars,
            title=title.strip(),
            tags=tag_line,
            content=truncated,
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一名中文技术写作助手，擅长在 50-120 字之间精准概括重点。"
                        "摘要必须为单段自然语言，不得包含项目符号、Markdown 符号或额外提示。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
            except RequestException as exc:
                if attempt + 1 >= self.max_retries:
                    print(f"[AI summary] DeepSeek 请求失败（{slug}）：{exc}")
                    return None
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"[AI summary] 无法解析 DeepSeek 响应（{slug}）。")
                return None
            summary = self._extract_content(data)
            if summary:
                return clamp_summary(summary, limit=self.max_output_chars)
            print(f"[AI summary] DeepSeek 返回空摘要（{slug}）。")
            return None
        return None

    def _extract_content(self, payload: Dict[str, Any]) -> Optional[str]:
        choices = payload.get("choices")
        if not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not message:
            return None
        content = message.get("content")
        return self._normalize_output(content)

    def _normalize_output(self, text: Any) -> Optional[str]:
        if not isinstance(text, str):
            return None
        cleaned = text.strip()
        cleaned = re.sub(r"^(?:摘要|总结|概述|Summary)[:：\s]*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None


def write_markdown_with_front_matter(path: Path, front_matter: Dict[str, Any], body: str) -> None:
    yaml_block = yaml.safe_dump(front_matter, allow_unicode=True, sort_keys=False).strip()
    body_content = body.lstrip("\n")
    if body_content:
        new_text = f"---\n{yaml_block}\n---\n\n{body_content.rstrip()}\n"
    else:
        new_text = f"---\n{yaml_block}\n---\n"
    path.write_text(new_text, encoding="utf-8")


def to_absolute_url(site_url: str | None, url: str) -> str | None:
    if not site_url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    root = site_url.rstrip("/")
    if url == "/":
        return root + "/"
    return f"{root}/{url.lstrip('/')}"


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
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
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
            "pymdownx.superfences",
            "pymdownx.highlight",
        ],
        extension_configs={
            "codehilite": {
                "guess_lang": True,
                "noclasses": False,
                "pygments_style": "default",
                "linenums": False,
            },
            "toc": {
                "permalink": False,
            },
            "pymdownx.superfences": {
                "preserve_tabs": True,
                "css_class": "codehilite",
            },
            "pymdownx.highlight": {
                "guess_lang": False,
                "noclasses": False,
                "pygments_style": "default",
                "pygments_lang_class": True,
                "css_class": "codehilite",
            },
        },
        tab_length=2,
    )
    return md.convert(raw_markdown)


def summarize(description: str, html_content: str) -> str:
    if description:
        normalized_description = clamp_summary(description)
        if normalized_description:
            return normalized_description
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
    cleaned = re.sub(r"\s+", " ", joined).strip()
    if not cleaned:
        return "这篇文章暂无摘要，欢迎点击阅读全文了解详情。"
    return clamp_summary(cleaned)


def parse_pinned_meta(front_matter: Dict[str, Any]) -> Tuple[bool, int]:
    raw_flag = front_matter.get("pinned")
    raw_priority = front_matter.get("pinned_priority")
    pinned = False
    priority = 1000

    def coerce_int(value: Any) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return priority

    if isinstance(raw_flag, bool):
        pinned = raw_flag
    elif isinstance(raw_flag, (int, float)):
        pinned = raw_flag != 0
        if pinned:
            priority = int(raw_flag)
    elif isinstance(raw_flag, str):
        normalized = raw_flag.strip().lower()
        truthy = {"true", "yes", "on"}
        falsy = {"false", "no", "off"}
        if normalized in truthy:
            pinned = True
        elif normalized in falsy or not normalized:
            pinned = False
        else:
            try:
                priority = int(float(normalized))
                pinned = True
            except ValueError:
                pinned = False

    if raw_priority is not None:
        coerced = coerce_int(raw_priority)
        priority = coerced

    if pinned and priority == 1000:
        priority = 0

    if not pinned:
        priority = 1000

    return pinned, priority


def strip_html_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_first_heading(markdown_body: str) -> str | None:
    match = HEADING_PATTERN.search(markdown_body)
    if match:
        return match.group("title").strip()
    return None


def to_tag_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [part.strip() for part in re.split(r"[,;/]", raw) if part.strip()]
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(item).strip() for item in raw if str(item).strip()]
    else:
        return []
    seen = set()
    normalized: List[str] = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(part)
    return normalized

def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def estimate_reading_time(word_count: int, words_per_minute: int = 220) -> int:
    if word_count <= 0:
        return 1
    return max(1, (word_count + words_per_minute - 1) // words_per_minute)


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    cleaned = re.sub(r"[\s_-]+", "-", cleaned)
    return cleaned or "tag"


def update_collection_state(raw: Any, folder: Path, state: CollectionState) -> CollectionState:
    if raw in (None, ""):
        return state
    config = state.config
    anchor_path = state.anchor_path

    if isinstance(raw, bool):
        if raw:
            return CollectionState(config=CollectionConfig(), anchor_path=folder)
        return CollectionState(config=None, anchor_path=None)

    if isinstance(raw, dict):
        new_config = config
        if new_config is None:
            new_config = CollectionConfig()
            anchor_path = folder

        if "enabled" in raw:
            enabled_value = coerce_bool(raw.get("enabled"), new_config.enabled)
            if not enabled_value:
                return CollectionState(config=None, anchor_path=None)
            new_config.enabled = True
            anchor_path = folder
        elif config is None:
            new_config.enabled = True
            anchor_path = folder

        if "title" in raw:
            value = str(raw.get("title", "")).strip()
            new_config.title = value or None

        if "description" in raw:
            value = str(raw.get("description", "")).strip()
            new_config.description = value or None

        if "order" in raw:
            order_value = raw.get("order")
            if order_value not in (None, ""):
                try:
                    new_config.order = int(float(order_value))
                except (TypeError, ValueError):
                    pass

        if "tags" in raw:
            new_config.tags = to_tag_list(raw.get("tags"))

        return CollectionState(config=new_config, anchor_path=anchor_path)

    return state


def default_collection_title(segments: List[str]) -> str:
    if not segments:
        return "合集"
    label = segments[-1]
    return label.replace("-", " ").strip().title() or "合集"


def default_collection_description(count: int, latest: dt.date) -> str:
    latest_label = latest.strftime("%Y年%m月%d日")
    return f"共 {count} 篇文章，最近更新于 {latest_label}。"


def discover_posts(
    source_dir: Path,
    include_drafts: bool,
    base_url: str,
    summarizer: Optional[LLMSummarizer] = None,
) -> Tuple[List[Post], Dict[str, CollectionConfig]]:
    posts_dir = source_dir / "posts"
    if not posts_dir.exists():
        return [], {}
    posts: List[Post] = []
    folder_meta_cache: Dict[Path, Dict[str, Any]] = {}
    collection_configs: Dict[str, CollectionConfig] = {}

    def load_folder_meta(folder: Path) -> Dict[str, Any]:
        if folder in folder_meta_cache:
            return folder_meta_cache[folder]
        meta_path = folder / POST_FOLDER_META_FILENAME
        data: Dict[str, Any] = {}
        if meta_path.is_file():
            try:
                loaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[meta] 无法读取 {meta_path}: {exc}")
                loaded = None
            if isinstance(loaded, dict):
                data = loaded
            elif loaded not in (None, ""):
                print(f"[meta] 忽略 {meta_path}: 需要 YAML 字典类型。")
        folder_meta_cache[folder] = data
        return data

    def collect_folder_chain(folder: Path) -> List[Path]:
        chain: List[Path] = []
        current = folder
        while True:
            if current == posts_dir or posts_dir in current.parents:
                chain.append(current)
                if current == posts_dir:
                    break
                current = current.parent
                continue
            break
        chain.reverse()
        return chain

    for md_path in sorted(posts_dir.rglob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        front_matter_raw, body = extract_front_matter(raw)
        if not isinstance(front_matter_raw, dict):
            front_matter = {}
        else:
            front_matter = dict(front_matter_raw)
        front_matter_modified = False
        ai_summary_notice: Optional[str] = None

        relative_path = md_path.relative_to(posts_dir)
        folder_segments = list(relative_path.parts[:-1])

        folder_chain = collect_folder_chain(md_path.parent)
        folder_defaults: Dict[str, Any] = {}
        folder_tags: List[str] = []
        collection_state = CollectionState(config=None, anchor_path=None)
        collection_path: Optional[str] = None

        for folder_path in folder_chain:
            meta = load_folder_meta(folder_path)
            if not isinstance(meta, dict) or not meta:
                continue
            meta_tags = to_tag_list(meta.get("tags"))
            if meta_tags:
                folder_tags.extend(meta_tags)
            for key, value in meta.items():
                if key in {"tags", COLLECTION_META_KEY}:
                    continue
                if key not in folder_defaults:
                    folder_defaults[key] = value
            collection_state = update_collection_state(meta.get(COLLECTION_META_KEY), folder_path, collection_state)

        if collection_state.config and collection_state.anchor_path:
            config = collection_state.config
            if config.enabled:
                try:
                    relative_anchor = collection_state.anchor_path.relative_to(posts_dir)
                except ValueError:
                    relative_anchor = Path()
                anchor_segments = [segment for segment in relative_anchor.parts if segment]
                if anchor_segments:
                    collection_path = "/".join(anchor_segments)
                    existing_cfg = collection_configs.get(collection_path)
                    if existing_cfg:
                        if config.title and not existing_cfg.title:
                            existing_cfg.title = config.title
                        if config.description and not existing_cfg.description:
                            existing_cfg.description = config.description
                        if config.order is not None and existing_cfg.order is None:
                            existing_cfg.order = config.order
                        if config.tags and not existing_cfg.tags:
                            existing_cfg.tags = list(config.tags)
                    else:
                        collection_configs[collection_path] = CollectionConfig(
                            enabled=True,
                            title=config.title,
                            description=config.description,
                            order=config.order,
                            tags=list(config.tags),
                        )
        for key, value in folder_defaults.items():
            if key not in front_matter:
                front_matter[key] = value
                front_matter_modified = True

        original_tags_raw = front_matter.get("tags")
        normalized_tags = to_tag_list(original_tags_raw)
        if original_tags_raw != normalized_tags:
            front_matter["tags"] = normalized_tags
            front_matter_modified = True
        combined_tags = list(normalized_tags)
        seen_tags = {tag.lower() for tag in combined_tags}
        for tag in folder_tags:
            lower = tag.lower()
            if lower in seen_tags:
                continue
            combined_tags.append(tag)
            seen_tags.add(lower)
        if front_matter.get("tags") != combined_tags:
            front_matter["tags"] = combined_tags
            front_matter_modified = True

        raw_slug = front_matter.get("slug")
        slug_candidate = str(raw_slug).strip() if isinstance(raw_slug, str) else ""
        if not slug_candidate:
            slug_candidate = md_path.stem
        slug_candidate = slug_candidate.replace("/", "-").strip()
        if not slug_candidate:
            slug_candidate = md_path.stem or "post"
        slug_segments = folder_segments + [slug_candidate]
        slug = slug_candidate

        title = front_matter.get("title")
        if not title:
            title = extract_first_heading(body)
        if not title:
            title = slug.replace("-", " ").strip().title() or md_path.name

        date_value = front_matter.get("date")
        if not date_value:
            modified = dt.datetime.fromtimestamp(md_path.stat().st_mtime, dt.timezone.utc)
            date_value = modified.date()
        date = parse_date(date_value)

        draft = bool(front_matter.get("draft", False))
        if draft and not include_drafts:
            continue

        html = render_markdown(body)
        tags = to_tag_list(front_matter.get("tags"))
        word_count = count_words(body)
        reading_time = estimate_reading_time(word_count)
        description_seed = (front_matter.get("description") or front_matter.get("excerpt", "") or "").strip()
        if not description_seed and summarizer:
            ai_summary = summarizer.generate_summary(
                title=title,
                plain_text=strip_html_tags(html),
                tags=tags,
                slug=slug,
                item_type="post",
            )
            if ai_summary:
                front_matter["description"] = ai_summary
                description_seed = ai_summary
                front_matter_modified = True
                ai_summary_notice = f"[AI summary] 已为 {md_path.relative_to(source_dir)} 生成摘要。"

        description = summarize(description_seed, html)
        pinned, pinned_priority = parse_pinned_meta(front_matter)

        if not isinstance(raw_slug, str) or raw_slug.strip() != slug:
            front_matter["slug"] = slug
            front_matter_modified = True

        output_path = PUBLIC_DIR / "posts" / Path(*slug_segments) / "index.html"
        posts.append(
            Post(
                title=title,
                date=date,
                slug=slug,
                slug_segments=slug_segments,
                group_segments=folder_segments,
                description=description,
                content_markdown=body,
                content_html=html,
                draft=draft,
                source_path=md_path,
                output_path=output_path,
                base_url=base_url,
                tags=tags,
                word_count=word_count,
                reading_time_minutes=reading_time,
                pinned=pinned,
                pinned_priority=pinned_priority,
                collection_path=collection_path,
            )
        )

        if front_matter_modified:
            try:
                write_markdown_with_front_matter(md_path, front_matter, body)
                if ai_summary_notice:
                    print(ai_summary_notice)
            except Exception as exc:
                print(f"[build] 无法写入更新到 {md_path}: {exc}")
        elif ai_summary_notice:
            print(ai_summary_notice)
    posts.sort(key=lambda post: post.date, reverse=True)
    return posts, collection_configs


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)


def discover_pages(
    source_dir: Path,
    base_url: str,
    summarizer: Optional[LLMSummarizer] = None,
) -> List[Page]:
    pages_dir = source_dir / "pages"
    if not pages_dir.exists():
        return []
    pages: List[Page] = []
    for md_path in sorted(pages_dir.rglob("*.md")):
        raw = md_path.read_text(encoding="utf-8")
        front_matter, body = extract_front_matter(raw)
        title = front_matter.get("title") or extract_first_heading(body) or md_path.stem.replace("-", " ").title()
        slug = front_matter.get("slug") or md_path.relative_to(pages_dir).with_suffix("").as_posix()
        slug = slug.strip("/")
        description_seed = (front_matter.get("description") or front_matter.get("excerpt", "") or "").strip()
        html_content = render_markdown(body)
        if not description_seed and summarizer:
            ai_summary = summarizer.generate_summary(
                title=title,
                plain_text=strip_html_tags(html_content),
                tags=[],
                slug=slug,
                item_type="page",
            )
            if ai_summary:
                front_matter["description"] = ai_summary
                description_seed = ai_summary
                try:
                    write_markdown_with_front_matter(md_path, front_matter, body)
                    relative_path = md_path.relative_to(source_dir)
                    print(f"[AI summary] 已为 {relative_path} 生成摘要。")
                except Exception as exc:
                    print(f"[AI summary] 写回摘要到 {md_path} 失败：{exc}")
        description = summarize(description_seed, html_content)
        output_path = PUBLIC_DIR / slug / "index.html"
        show_in_nav = bool(front_matter.get("nav", True))
        nav_order = int(front_matter.get("nav_order", 100))
        pages.append(
            Page(
                title=title,
                slug=slug,
                description=description,
                content_markdown=body,
                content_html=html_content,
                source_path=md_path,
                output_path=output_path,
                base_url=base_url,
                show_in_nav=show_in_nav,
                nav_order=nav_order,
            )
        )
    pages.sort(key=lambda page: (page.nav_order, page.title.lower()))
    return pages


def collect_tags(posts: List[Post], base_url: str) -> Dict[str, TagInfo]:
    tags: Dict[str, TagInfo] = {}
    for post in posts:
        for tag in post.tags:
            slug = slugify(tag)
            url = join_url(base_url, "tags", slug, trailing_slash=True)
            if slug not in tags:
                tags[slug] = TagInfo(name=tag, slug=slug, url=url, posts=[])
            tags[slug].posts.append(post)
    for info in tags.values():
        info.posts.sort(key=lambda post: post.date, reverse=True)
    return dict(sorted(tags.items(), key=lambda item: item[1].name.lower()))


def find_related_posts(target: Post, posts: List[Post], limit: int = 3) -> List[Post]:
    if not target.tags:
        return []
    target_tags = {tag.lower() for tag in target.tags}
    scored: List[Tuple[int, dt.date, Post]] = []
    for other in posts:
        if other is target:
            continue
        if not other.tags:
            continue
        overlap = target_tags.intersection({tag.lower() for tag in other.tags})
        if not overlap:
            continue
        scored.append((len(overlap), other.date, other))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [entry[2] for entry in scored[:limit]]


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


def group_posts_by_year(posts: List[Post]) -> List[Tuple[int, List[Post]]]:
    buckets: Dict[int, List[Post]] = collections.defaultdict(list)
    for post in posts:
        buckets[post.date.year].append(post)
    groups: List[Tuple[int, List[Post]]] = []
    for year, year_posts in buckets.items():
        sorted_posts = sorted(year_posts, key=lambda post: post.date, reverse=True)
        groups.append((year, sorted_posts))
    groups.sort(key=lambda item: item[0], reverse=True)
    return groups


def build_collection_entries(
    collection_configs: Dict[str, CollectionConfig],
    posts: List[Post],
    base_url: str,
) -> List[CollectionEntry]:
    if not collection_configs:
        return []
    grouped_posts: Dict[str, List[Post]] = collections.defaultdict(list)
    for post in posts:
        if post.collection_path:
            grouped_posts[post.collection_path].append(post)

    entries: List[CollectionEntry] = []
    for path, config in collection_configs.items():
        post_items = grouped_posts.get(path, [])
        if not post_items:
            continue
        sorted_posts = sorted(post_items, key=lambda item: item.date, reverse=True)
        latest_date = sorted_posts[0].date
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            continue
        title = config.title or default_collection_title(segments)
        description = config.description or default_collection_description(len(sorted_posts), latest_date)
        tags = list(config.tags)
        if not tags:
            counter: collections.Counter[str] = collections.Counter()
            tag_lookup: Dict[str, str] = {}
            for post in sorted_posts:
                for tag in post.tags:
                    key = tag.lower()
                    counter[key] += 1
                    if key not in tag_lookup:
                        tag_lookup[key] = tag
            tags = [tag_lookup[key] for key, _ in counter.most_common(4)]

        entries.append(
            CollectionEntry(
                title=title,
                description=description,
                slug_segments=segments,
                group_segments=segments,
                base_url=base_url,
                posts=sorted_posts,
                tags=tags,
                order=config.order,
                collection_path=path,
                latest_date=latest_date,
            )
        )

    def entry_sort_key(entry: CollectionEntry) -> Tuple[int, int]:
        order_value = entry.order if entry.order is not None else 1000
        return (order_value, -entry.date.toordinal())

    entries.sort(key=entry_sort_key)
    return entries


def home_sort_key(item: Any) -> Tuple[int, int]:
    order_attr = getattr(item, "order", None)
    order_value = order_attr if isinstance(order_attr, int) else 1000
    date_attr = getattr(item, "date", None)
    if isinstance(date_attr, dt.date):
        date_ord = -date_attr.toordinal()
    else:
        date_ord = -dt.date.today().toordinal()
    return (order_value, date_ord)


def build_navigation(
    config: Dict[str, Any],
    pages: List[Page],
    base_url: str,
    has_tags: bool,
    has_posts: bool,
) -> List[Dict[str, str]]:
    nav_items: List[Dict[str, str]] = []

    def add_link(label: str, url: str) -> None:
        if not label or not url:
            return
        nav_items.append({"label": label, "url": url})

    custom_nav = config.get("nav_links") or config.get("nav")
    if custom_nav:
        for item in custom_nav:
            label = item.get("label") if isinstance(item, dict) else None
            url_value = item.get("url") if isinstance(item, dict) else None
            if not (label and url_value):
                continue
            if url_value.startswith("http://") or url_value.startswith("https://"):
                add_link(label, url_value)
            else:
                segments = [segment for segment in url_value.strip("/").split("/") if segment]
                url = join_url(base_url, *segments, trailing_slash=url_value.endswith("/"))
                add_link(label, url)
        return nav_items

    add_link("首页", join_url(base_url, trailing_slash=True))
    if has_posts:
        add_link("归档", join_url(base_url, "archive", trailing_slash=True))
    nav_show_tags = config.get("nav_show_tags")
    if nav_show_tags == "auto":
        show_tags_link = has_tags
    elif nav_show_tags is None:
        show_tags_link = True
    else:
        show_tags_link = bool(nav_show_tags)
    if show_tags_link:
        add_link("标签", join_url(base_url, "tags", trailing_slash=True))
    for page in pages:
        if page.show_in_nav:
            add_link(page.title, page.url)
    return nav_items


def render_tag_pages(
    tags: Dict[str, TagInfo],
    env: Environment,
    config: Dict[str, Any],
    site_url: str | None,
) -> List[Path]:
    rendered: List[Path] = []
    tag_index_template = env.get_template("tag_index.html")
    tag_detail_template = env.get_template("tag_detail.html")
    tag_list = [info for _, info in tags.items()]

    index_path = PUBLIC_DIR / "tags" / "index.html"
    ensure_dirs(index_path)
    description = (
        f"共收录 {len(tag_list)} 个标签，来自 {config.get('title', '本站')}。"
        if tag_list
        else "尚未设置标签，给文章添加 tags 元数据即可启用标签页。"
    )
    index_html = tag_index_template.render(
        site=config,
        tags=tag_list,
        page_title="全部标签",
        page_description=description,
        canonical_url=to_absolute_url(
            site_url, join_url(config.get("base_url", "/"), "tags", trailing_slash=True)
        ),
    )
    index_path.write_text(index_html, encoding="utf-8")
    rendered.append(index_path)

    if not tag_list:
        return rendered

    for info in tag_list:
        detail_path = PUBLIC_DIR / "tags" / info.slug / "index.html"
        ensure_dirs(detail_path)
        detail_html = tag_detail_template.render(
            site=config,
            tag=info,
            posts=info.posts,
            page_title=f"标签：{info.name}",
            page_description=f"{info.name} 标签下的文章与笔记。",
            canonical_url=to_absolute_url(site_url, info.url),
        )
        detail_path.write_text(detail_html, encoding="utf-8")
        rendered.append(detail_path)
    return rendered


def render_pages(pages: List[Page], env: Environment, config: Dict[str, Any], site_url: str | None) -> List[Path]:
    if not pages:
        return []
    rendered: List[Path] = []
    template = env.get_template("page.html")
    for page in pages:
        ensure_dirs(page.output_path)
        html_output = template.render(
            site=config,
            page=page,
            page_title=page.title,
            page_description=page.description,
            canonical_url=to_absolute_url(site_url, page.url),
        )
        page.output_path.write_text(html_output, encoding="utf-8")
        rendered.append(page.output_path)
    return rendered


def render_collection_pages(
    collections: List[CollectionEntry],
    env: Environment,
    config: Dict[str, Any],
    site_url: str | None,
) -> List[Path]:
    if not collections:
        return []
    rendered: List[Path] = []
    template = env.get_template("collection.html")
    for entry in collections:
        output_path = PUBLIC_DIR / "posts" / Path(*entry.slug_segments) / "index.html"
        ensure_dirs(output_path)
        html_output = template.render(
            site=config,
            collection=entry,
            posts=entry.posts,
            page_title=entry.title,
            page_description=entry.description,
            canonical_url=to_absolute_url(site_url, entry.url),
        )
        output_path.write_text(html_output, encoding="utf-8")
        rendered.append(output_path)
    return rendered


def render_archive(
    posts: List[Post],
    env: Environment,
    config: Dict[str, Any],
    site_url: str | None,
) -> Path | None:
    if not posts:
        return None
    archive_template = env.get_template("archive.html")
    archive_groups = group_posts_by_year(posts)
    output_path = PUBLIC_DIR / "archive" / "index.html"
    ensure_dirs(output_path)
    archive_html = archive_template.render(
        site=config,
        groups=archive_groups,
        page_title="文章归档",
        page_description="按时间顺序浏览所有文章。",
        canonical_url=to_absolute_url(site_url, join_url(config.get("base_url", "/"), "archive", trailing_slash=True)),
    )
    output_path.write_text(archive_html, encoding="utf-8")
    return output_path


def build_search_index(posts: List[Post], pages: List[Page], base_url: str) -> Path | None:
    if not posts and not pages:
        return None
    records: List[Dict[str, Any]] = []

    def truncate(text: str, limit: int = 320) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3].rstrip() + "..."

    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    for post in posts:
        content_text = clean_text(strip_html_tags(post.content_html))
        summary = truncate(content_text)
        records.append(
            {
                "type": "post",
                "title": post.title,
                "url": post.url,
                "description": post.description,
                "summary": summary,
                "content": truncate(content_text, 6000),
                "tags": post.tags,
                "date": post.date.isoformat(),
                "reading_time": post.reading_time_minutes,
            }
        )

    for page in pages:
        content_text = clean_text(strip_html_tags(page.content_html))
        summary = truncate(content_text)
        records.append(
            {
                "type": "page",
                "title": page.title,
                "url": join_url(base_url, page.slug, trailing_slash=True),
                "description": page.description,
                "summary": summary,
                "content": truncate(content_text, 6000),
                "tags": [],
            }
        )

    index_path = PUBLIC_DIR / "search.json"
    ensure_dirs(index_path)
    index_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def render_search_page(
    posts: List[Post],
    pages: List[Page],
    env: Environment,
    config: Dict[str, Any],
    site_url: str | None,
) -> Path | None:
    if not posts and not pages:
        return None
    template = env.get_template("search.html")
    output_path = PUBLIC_DIR / "search" / "index.html"
    ensure_dirs(output_path)
    base_url = config.get("base_url", "/")
    search_index_url = join_url(base_url, "search.json")
    html_output = template.render(
        site=config,
        page_title="站内搜索",
        page_description="通过关键字查找文章与页面。",
        canonical_url=to_absolute_url(site_url, join_url(base_url, "search", trailing_slash=True)),
        search_index_url=search_index_url,
    )
    output_path.write_text(html_output, encoding="utf-8")
    return output_path


def render_not_found_page(
    env: Environment,
    config: Dict[str, Any],
    site_url: str | None,
    search_enabled: bool,
) -> Path:
    template = env.get_template("404.html")
    output_path = PUBLIC_DIR / "404.html"
    ensure_dirs(output_path)
    html_output = template.render(
        site=config,
        page_title="页面未找到",
        page_description="抱歉，您访问的页面不存在。",
        canonical_url=None,
        search_enabled=search_enabled,
    )
    output_path.write_text(html_output, encoding="utf-8")
    return output_path


def write_feed(posts: List[Post], config: Dict[str, Any], site_url: str | None) -> Path | None:
    if not config.get("rss_enabled", True):
        return None
    if not site_url or not posts:
        return None
    feed_path = PUBLIC_DIR / "feed.xml"
    ensure_dirs(feed_path)
    site_title = config.get("title", "AutoBlog")
    site_description = config.get("description", "Static blog feed")
    feed_url = join_url(site_url, "feed.xml")
    site_link = site_url
    items: List[str] = []
    feed_xml = ""
    for post in posts:
        item_link = join_url(site_url, "posts", *post.slug_segments, trailing_slash=True)
        pub_date = format_datetime(dt.datetime.combine(post.date, dt.time.min, tzinfo=dt.timezone.utc))
        items.append(
            """
        <item>
            <title>{title}</title>
            <link>{link}</link>
            <guid>{link}</guid>
            <pubDate>{pub_date}</pubDate>
            <description>{description}</description>
        </item>
        """.strip().format(
                title=html.escape(post.title),
                link=html.escape(item_link),
                pub_date=pub_date,
                description=html.escape(post.description),
            )
        )
        items_xml = "\n    ".join(items) if items else ""
        feed_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\">
  <channel>
    <title>{html.escape(site_title)}</title>
    <link>{html.escape(site_link)}</link>
    <description>{html.escape(site_description)}</description>
        <atom:link xmlns:atom=\"http://www.w3.org/2005/Atom\" href=\"{html.escape(feed_url)}\" rel=\"self\" type=\"application/rss+xml\" />
        {items_xml}
  </channel>
</rss>
"""
    feed_path.write_text(feed_xml, encoding="utf-8")
    return feed_path


def write_sitemap(
    posts: List[Post],
    pages: List[Page],
    tags: Dict[str, TagInfo],
    config: Dict[str, Any],
    site_url: str | None,
) -> Path | None:
    if not site_url:
        return None
    urls: List[str] = []

    def add_url(path: str, lastmod: str | None = None) -> None:
        trailing = path.endswith("/")
        segments = [segment for segment in path.strip("/").split("/") if segment]
        loc = join_url(site_url, *segments, trailing_slash=trailing) if path != "/" else site_url
        entry = "  <url>\n    <loc>{}</loc>".format(html.escape(loc))
        if lastmod:
            entry += "\n    <lastmod>{}</lastmod>".format(lastmod)
        entry += "\n  </url>"
        urls.append(entry)

    add_url("/")
    if posts:
        add_url("archive/", posts[0].date.isoformat())
    if tags:
        add_url("tags/", None)
        for info in tags.values():
            lastmod = info.posts[0].date.isoformat() if info.posts else None
            add_url(f"tags/{info.slug}/", lastmod)
    for post in posts:
        add_url("/".join(["posts", *post.slug_segments]) + "/", post.date.isoformat())
    for page in pages:
        add_url(f"{page.slug}/", None)

    sitemap_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{entries}
</urlset>
""".format(entries="\n".join(urls))
    sitemap_path = PUBLIC_DIR / "sitemap.xml"
    ensure_dirs(sitemap_path)
    sitemap_path.write_text(sitemap_xml, encoding="utf-8")
    return sitemap_path


def run_git(command: List[str], cwd: Path | None = None, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    kwargs = {"cwd": cwd, "check": True, "text": True}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    return subprocess.run(["git", *command], **kwargs)


def resolve_remote_url(remote_name: str | None, config: Dict[str, Any]) -> str:
    explicit = (config.get("github_remote_url") or "").strip()
    if explicit:
        return explicit
    if remote_name:
        try:
            result = run_git(["remote", "get-url", remote_name], cwd=ROOT, capture_output=True)
            url = (result.stdout or "").strip()
            if url:
                return url
        except subprocess.CalledProcessError:
            pass
    repo = (config.get("github_repo") or "").strip()
    if repo:
        return f"git@github.com:{repo}.git"
    raise RuntimeError(
        "Unable to determine Git remote URL. Set github_repo or github_remote_url in source/config.yaml."
    )


def copy_public_contents(public_dir: Path, target_dir: Path) -> None:
    for item in public_dir.iterdir():
        destination = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)


def push_public_directory(
    public_dir: Path,
    remote_url: str,
    branch: str,
    commit_message: str,
    dry_run: bool,
) -> bool:
    if not public_dir.exists():
        raise RuntimeError("public/ directory does not exist. Run the builder first.")
    if not any(public_dir.iterdir()):
        raise RuntimeError("public/ directory is empty; nothing to deploy.")

    with tempfile.TemporaryDirectory(prefix="autoblog-deploy-") as temp_path_str:
        temp_path = Path(temp_path_str)
        copy_public_contents(public_dir, temp_path)
        try:
            run_git(["init", "-b", branch], cwd=temp_path)
        except subprocess.CalledProcessError:
            run_git(["init"], cwd=temp_path)
            run_git(["checkout", "-b", branch], cwd=temp_path)
        run_git(["config", "user.name", "AutoBlog Deploy"], cwd=temp_path)
        run_git(["config", "user.email", "autoblog@example.com"], cwd=temp_path)
        run_git(["add", "--all"], cwd=temp_path)
        status = run_git(["status", "--porcelain"], cwd=temp_path, capture_output=True)
        if not (status.stdout or "").strip():
            print("No changes detected; skipping deployment.")
            return False
        run_git(["commit", "-m", commit_message], cwd=temp_path)
        run_git(["remote", "add", "origin", remote_url], cwd=temp_path)
        if dry_run:
            print("Dry run enabled. Skipping git push.")
            return False
        run_git(["push", "origin", f"HEAD:{branch}", "--force"], cwd=temp_path)
        return True
    return False


def deploy_to_github(config: Dict[str, Any], args: argparse.Namespace) -> None:
    branch = (args.branch or config.get("github_branch") or "").strip()
    if not branch:
        raise RuntimeError("Deployment branch is not set. Use --branch or configure github_branch in config.yaml.")
    remote_name = args.remote or config.get("github_remote")
    remote_url = resolve_remote_url(remote_name, config)
    commit_message = args.message or f"AutoBlog deploy {dt.datetime.now(dt.timezone.utc).isoformat()}"
    print(f"\nDeploying public/ to {remote_url} (branch: {branch})")
    pushed = push_public_directory(PUBLIC_DIR, remote_url, branch, commit_message, args.dry_run)
    if args.dry_run:
        print("Deployment dry run complete.")
    elif pushed:
        print("Deployment completed.")
    else:
        print("Deployment skipped.")


def build_site(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.skip_clean and PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    config = load_site_config(SOURCE_DIR)
    base_url = config.get("base_url", "/")
    site_url = config.get("site_url") or ""
    summarizer = LLMSummarizer.from_config(config)
    if summarizer:
        print("AI 摘要功能已启用（DeepSeek）。")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["site"] = config
    env.globals["build_time"] = dt.datetime.now(dt.timezone.utc)
    env.globals["base_url"] = base_url
    env.globals["site_url"] = site_url
    url_builder = make_url_builder(base_url)
    env.globals["url_for"] = url_builder
    env.filters["slugify"] = slugify
    env.globals["tag_url"] = lambda name: join_url(base_url, "tags", slugify(name), trailing_slash=True)
    env.globals["search_index_url"] = join_url(base_url, "search.json")

    posts, collection_configs = discover_posts(
        SOURCE_DIR,
        include_drafts=args.drafts,
        base_url=base_url,
        summarizer=summarizer,
    )
    pages = discover_pages(SOURCE_DIR, base_url, summarizer=summarizer)
    collection_entries = build_collection_entries(collection_configs, posts, base_url)
    tags = collect_tags(posts, base_url)
    nav_links = build_navigation(config, pages, base_url, has_tags=bool(tags), has_posts=bool(posts))
    env.globals["nav_links"] = nav_links
    env.globals["all_pages"] = pages
    env.globals["all_tags"] = tags

    def build_post_groups(post_items: List[Post]) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Post]] = collections.defaultdict(list)
        for item in post_items:
            key = item.group_path
            groups[key].append(item)
        grouped_list: List[Dict[str, Any]] = []
        for path_key, grouped_posts in groups.items():
            sorted_posts = sorted(grouped_posts, key=lambda post: post.date, reverse=True)
            segments = [segment for segment in path_key.split("/") if segment] if path_key else []
            label = segments[-1] if segments else ""
            grouped_list.append(
                {
                    "path": path_key,
                    "segments": segments,
                    "label": label,
                    "posts": sorted_posts,
                }
            )
        grouped_list.sort(key=lambda entry: entry["path"] or "")
        return grouped_list

    env.globals["post_groups"] = build_post_groups(posts)

    index_template = env.get_template("index.html")
    post_template = env.get_template("post.html")

    rendered_files: List[Path] = []

    for index, post in enumerate(posts):
        ensure_dirs(post.output_path)
        tag_links = [
            {"name": tag, "url": join_url(base_url, "tags", slugify(tag), trailing_slash=True)}
            for tag in post.tags
        ]
        newer_post = posts[index - 1] if index > 0 else None
        older_post = posts[index + 1] if index + 1 < len(posts) else None
        related_posts = find_related_posts(post, posts)
        html = post_template.render(
            post=post,
            site=config,
            page_title=post.title,
            page_description=post.description,
            canonical_url=to_absolute_url(site_url, post.url),
            tag_links=tag_links,
            newer_post=newer_post,
            older_post=older_post,
            related_posts=related_posts,
        )
        post.output_path.write_text(html, encoding="utf-8")
        rendered_files.append(post.output_path)

    tag_lookup = {info.name: info.url for info in tags.values()}
    visible_posts = [post for post in posts if not post.collection_path]
    pinned_posts = sorted(
        (post for post in visible_posts if post.pinned),
        key=lambda post: (post.pinned_priority, -post.date.toordinal()),
    )
    combined_items = sorted(visible_posts + collection_entries, key=home_sort_key)

    if pinned_posts:
        hero_post = pinned_posts[0]
        hero_label = "置顶文章"
    elif combined_items:
        hero_post = combined_items[0]
        hero_label = "文章合集" if getattr(hero_post, "is_collection", False) else "最新发布"
    else:
        hero_post = None
        hero_label = "最新发布"

    grid_posts: List[Any] = []
    if hero_post:
        if pinned_posts:
            for post in pinned_posts:
                if post is hero_post:
                    continue
                grid_posts.append(post)
        for item in combined_items:
            if item is hero_post:
                continue
            if item in grid_posts:
                continue
            grid_posts.append(item)
    else:
        grid_posts = combined_items

    index_html = index_template.render(
        hero_post=hero_post,
        hero_label=hero_label,
        grid_posts=grid_posts,
        site=config,
        page_title=None,
        page_description=config.get("description", ""),
        canonical_url=to_absolute_url(site_url, join_url(base_url, trailing_slash=True)),
        tag_lookup=tag_lookup,
        all_posts=posts,
        collection_entries=collection_entries,
    )
    index_path = PUBLIC_DIR / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    rendered_files.append(index_path)

    page_files = render_pages(pages, env, config, site_url)
    rendered_files.extend(page_files)

    tag_files = render_tag_pages(tags, env, config, site_url)
    rendered_files.extend(tag_files)

    collection_files = render_collection_pages(collection_entries, env, config, site_url)
    rendered_files.extend(collection_files)

    archive_path = render_archive(posts, env, config, site_url)
    if archive_path:
        rendered_files.append(archive_path)

    search_index_path = build_search_index(posts, pages, base_url)
    if search_index_path:
        rendered_files.append(search_index_path)

    search_page_path = render_search_page(posts, pages, env, config, site_url)
    if search_page_path:
        rendered_files.append(search_page_path)

    not_found_path = render_not_found_page(
        env,
        config,
        site_url,
        search_enabled=bool(search_page_path),
    )
    rendered_files.append(not_found_path)

    feed_path = write_feed(posts, config, site_url)
    if feed_path:
        rendered_files.append(feed_path)

    sitemap_path = write_sitemap(posts, pages, tags, config, site_url)
    if sitemap_path:
        rendered_files.append(sitemap_path)

    assets = copy_assets(SOURCE_DIR, PUBLIC_DIR)
    rendered_files.extend(assets)

    print("Wrote:")
    for path in rendered_files:
        print(f"  {path.relative_to(ROOT)}")
    return config


def main() -> None:
    args = parse_args()
    config = build_site(args)
    if args.deploy:
        deploy_to_github(config, args)


if __name__ == "__main__":
    main()
