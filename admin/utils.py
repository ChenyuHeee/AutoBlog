from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def posts_dir(self) -> Path:
        return self.source_dir / "posts"

    @property
    def pages_dir(self) -> Path:
        return self.source_dir / "pages"

    @property
    def public_dir(self) -> Path:
        return self.root / "public"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def assets_dir(self) -> Path:
        return self.source_dir / "assets"


class PathSecurityError(ValueError):
    pass


def resolve_under(root: Path, user_path: str) -> Path:
    """Resolve a user-provided path under a root directory, preventing traversal."""
    if not user_path:
        raise PathSecurityError("Empty path")
    candidate = (root / user_path).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PathSecurityError("Path escapes root") from exc
    return candidate


def list_files(root: Path, *, suffixes: Iterable[str] = ()) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if suffixes and path.suffix.lower() not in {s.lower() for s in suffixes}:
            continue
        files.append(path)
    files.sort(key=lambda p: p.as_posix().lower())
    return files
