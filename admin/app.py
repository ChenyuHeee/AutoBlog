from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import build as autoblog_build

from .utils import PathSecurityError, ProjectPaths, list_files, resolve_under


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATHS = ProjectPaths(root=PROJECT_ROOT)

app = FastAPI(title="AutoBlog Admin", version="0.1.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Serve admin static assets
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Serve generated site for preview
PATHS.public_dir.mkdir(parents=True, exist_ok=True)
app.mount("/preview", StaticFiles(directory=str(PATHS.public_dir), html=True), name="preview")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_build(*, include_drafts: bool = False, skip_clean: bool = False) -> dict[str, Any]:
    args = argparse.Namespace(
        skip_clean=skip_clean,
        drafts=include_drafts,
        deploy=False,
        remote=None,
        branch=None,
        dry_run=True,
        message=None,
    )
    return autoblog_build.build_site(args)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "now": dt.datetime.now(dt.timezone.utc),
        },
    )


@app.get("/theme", response_class=HTMLResponse)
def theme_index(request: Request):
    template_files = [
        p.relative_to(PROJECT_ROOT).as_posix()
        for p in list_files(PATHS.templates_dir, suffixes=(".html",))
    ]
    asset_files = [
        p.relative_to(PROJECT_ROOT).as_posix()
        for p in list_files(PATHS.assets_dir, suffixes=(".css", ".js", ".txt", ".xml"))
    ]
    return templates.TemplateResponse(
        "theme.html",
        {
            "request": request,
            "template_files": template_files,
            "asset_files": asset_files,
        },
    )


@app.get("/config", response_class=HTMLResponse)
def config_get(request: Request):
    config_path = PATHS.source_dir / "config.yaml"
    example_path = PATHS.source_dir / "config.yaml.example.yaml"
    content = _read_text(config_path) or _read_text(example_path)
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "config_path": config_path.relative_to(PROJECT_ROOT).as_posix(),
            "content": content,
        },
    )


@app.post("/config", response_class=HTMLResponse)
def config_save(request: Request, content: str = Form(...)):
    try:
        parsed = yaml.safe_load(content) or {}
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise ValueError("config.yaml must be a YAML mapping (dict)")
    except Exception as exc:
        return templates.TemplateResponse(
            "config.html",
            {
                "request": request,
                "config_path": (PATHS.source_dir / "config.yaml").relative_to(PROJECT_ROOT).as_posix(),
                "content": content,
                "error": f"YAML 解析失败：{exc}",
            },
            status_code=400,
        )

    path = PATHS.source_dir / "config.yaml"
    _write_text(path, content if content.endswith("\n") else content + "\n")
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "config_path": path.relative_to(PROJECT_ROOT).as_posix(),
            "content": _read_text(path),
            "success": "已保存 config.yaml",
        },
    )


@app.get("/content", response_class=HTMLResponse)
def content_index(request: Request):
    posts = [p.relative_to(PROJECT_ROOT).as_posix() for p in list_files(PATHS.posts_dir, suffixes=(".md",))]
    pages = [p.relative_to(PROJECT_ROOT).as_posix() for p in list_files(PATHS.pages_dir, suffixes=(".md",))]
    return templates.TemplateResponse(
        "content.html",
        {
            "request": request,
            "posts": posts,
            "pages": pages,
        },
    )


@app.get("/edit", response_class=HTMLResponse)
def edit_get(request: Request, path: str):
    try:
        candidate = resolve_under(PROJECT_ROOT, path)
        source_root = PATHS.source_dir.resolve()
        template_root = PATHS.templates_dir.resolve()
        if not (candidate.is_relative_to(source_root) or candidate.is_relative_to(template_root)):
            raise PathSecurityError("Path is not under an allowed directory")
        target = candidate
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content = _read_text(target)
    is_markdown = target.suffix.lower() == ".md"
    preview_html = ""
    if is_markdown:
        # Render only the body (strip front matter) to match builder.
        front, body = autoblog_build.extract_front_matter(content)
        preview_html = autoblog_build.render_markdown(body)

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "path": path,
            "content": content,
            "is_markdown": is_markdown,
            "preview_html": preview_html,
        },
    )


@app.post("/edit", response_class=HTMLResponse)
def edit_save(request: Request, path: str = Form(...), content: str = Form(...)):
    try:
        target = resolve_under(PROJECT_ROOT, path)
    except PathSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Allow only under source/ or templates/
    if not (target.is_relative_to(PATHS.source_dir.resolve()) or target.is_relative_to(PATHS.templates_dir.resolve())):
        raise HTTPException(status_code=400, detail="Editing this path is not allowed")

    if target.exists() and not target.is_file():
        raise HTTPException(status_code=400, detail="Target is not a file")

    _write_text(target, content)

    is_markdown = target.suffix.lower() == ".md"
    preview_html = ""
    if is_markdown:
        front, body = autoblog_build.extract_front_matter(content)
        preview_html = autoblog_build.render_markdown(body)

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "path": path,
            "content": _read_text(target),
            "is_markdown": is_markdown,
            "preview_html": preview_html,
            "success": "已保存",
        },
    )


@app.post("/build", response_class=HTMLResponse)
def build_now(request: Request, include_drafts: bool = Form(False), skip_clean: bool = Form(False)):
    try:
        _run_build(include_drafts=bool(include_drafts), skip_clean=bool(skip_clean))
    except Exception as exc:
        return templates.TemplateResponse(
            "build.html",
            {
                "request": request,
                "error": f"构建失败：{exc}",
            },
            status_code=500,
        )

    return templates.TemplateResponse(
        "build.html",
        {
            "request": request,
            "success": "构建完成：已更新 public/，可在 /preview/ 查看",
        },
    )


@app.get("/build", response_class=HTMLResponse)
def build_page(request: Request):
    return templates.TemplateResponse(
        "build.html",
        {
            "request": request,
        },
    )


@app.post("/api/render_markdown", response_class=HTMLResponse)
def api_render_markdown(content: str = Form(...)):
    front, body = autoblog_build.extract_front_matter(content)
    return HTMLResponse(autoblog_build.render_markdown(body))


@app.get("/health", response_class=PlainTextResponse)
def health():
    return PlainTextResponse("ok")
