from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Iterable


def list_files(root: Path, *, include_globs: Iterable[str]) -> list[Path]:
    if not root.exists():
        return []
    patterns = list(include_globs)
    results: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            results.append(path)
    results.sort(key=lambda p: p.as_posix().lower())
    return results


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
