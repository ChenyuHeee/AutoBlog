#!/usr/bin/env python3
"""Package the AutoBlog project into a shareable folder.

Copies the project into ``dist/<folder>`` while skipping generated artifacts
and any user-provided exclusion patterns listed in ``package_exclude.txt``.
Optional ``--zip`` flag creates a ``.zip`` archive next to the folder.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
DEFAULT_DEST_NAME = "autoblog-package"

DEFAULT_EXCLUDES = {
    ".git",
    ".gitmodules",
    ".github",
    ".venv",
    "__pycache__",
    "dist",
    "public",
    ".DS_Store",
}

DEFAULT_GLOB_EXCLUDES = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.swp",
    "Thumbs.db",
}

USER_EXCLUDE_FILE = ROOT / "package_exclude.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package the AutoBlog project for distribution")
    parser.add_argument(
        "--dest",
        default=DEFAULT_DEST_NAME,
        help="Name of the output folder created under dist/ (default: %(default)s)",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a .zip archive alongside the output folder",
    )
    return parser.parse_args()


def load_user_patterns() -> list[str]:
    if not USER_EXCLUDE_FILE.exists():
        return []
    patterns: list[str] = []
    for line in USER_EXCLUDE_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def should_skip(rel_path: Path, patterns: list[str]) -> bool:
    rel_str = rel_path.as_posix().lstrip("./")
    if not rel_str:
        return False
    parts = rel_str.split("/")
    if parts[0] in DEFAULT_EXCLUDES:
        return True
    if any(fnmatch.fnmatch(rel_str, pattern) for pattern in DEFAULT_GLOB_EXCLUDES):
        return True
    for pattern in patterns:
        norm = pattern.strip().lstrip("./")
        if not norm:
            continue
        if fnmatch.fnmatch(rel_str, norm):
            return True
        if rel_str == norm:
            return True
        if rel_str.startswith(f"{norm}/"):
            return True
    return False


def copy_project(destination: Path, patterns: list[str]) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in walk_filtered(ROOT, patterns):
        rel_dir = Path(root).relative_to(ROOT)
        target_dir = destination / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for file_name in files:
            rel_file = rel_dir / file_name
            src_path = ROOT / rel_file
            dst_path = destination / rel_file
            shutil.copy2(src_path, dst_path)


def walk_filtered(root: Path, patterns: list[str]):
    for current_root, dirs, files in os_walk_sorted(root):
        rel_dir = Path(current_root).relative_to(root)
        if should_skip(rel_dir, patterns):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not should_skip(rel_dir / d, patterns)]
        filtered_files = [f for f in files if not should_skip(rel_dir / f, patterns)]
        yield current_root, dirs, filtered_files


def os_walk_sorted(root: Path):
    for current_root, dirs, files in os.walk(root):
        if Path(current_root) == DIST_DIR:
            dirs[:] = []
            continue
        dirs.sort()
        files.sort()
        yield current_root, dirs, files


def make_zip_folder(destination: Path) -> Path:
    archive_path = destination.parent / f"{destination.name}.zip"
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_path.with_suffix("")), "zip", destination)
    return archive_path


def main() -> None:
    args = parse_args()
    user_patterns = load_user_patterns()
    output_dir = DIST_DIR / args.dest

    copy_project(output_dir, user_patterns)

    if args.zip:
        archive = make_zip_folder(output_dir)
        print(f"Created {archive}")
    else:
        print(f"Created {output_dir}")


if __name__ == "__main__":
    main()