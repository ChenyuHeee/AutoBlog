#!/usr/bin/env python3
"""Publish a sanitized open-source branch without affecting your local working copy.

What it does:
- Copies the current repo into a temporary directory (excluding personal paths).
- Creates a brand-new git history (single clean commit) to avoid leaking old secrets.
- Pushes that commit to a target branch on your existing GitHub remote.

Typical usage:
  python3 scripts/publish_open_source.py --remote origin --branch main --force

Notes:
- Edit scripts/publish_exclude.txt to control what gets removed.
- This script does NOT modify your current working tree.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EXCLUDES = {
    ".git",
    ".gitmodules",
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

DEFAULT_EXCLUDE_FILE_CANDIDATES = [
    ROOT / "scripts" / "publish_exclude.txt",
    ROOT / "package_exclude.txt",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a sanitized open-source branch (single-commit history)."
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote name to push to (default: %(default)s)",
    )
    parser.add_argument(
        "--branch",
        default="opensource",
        help="Remote branch name to push to (default: %(default)s)",
    )
    parser.add_argument(
        "--exclude-file",
        default="",
        help=(
            "Path to exclude patterns file. Defaults to scripts/publish_exclude.txt, "
            "fallback to package_exclude.txt."
        ),
    )
    parser.add_argument(
        "--message",
        default="chore: publish open-source snapshot",
        help="Commit message for the published snapshot",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force push to overwrite existing remote branch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the snapshot but do not push",
    )
    return parser.parse_args()


def run_git(args: list[str], *, cwd: Path, capture: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result


def die(message: str) -> None:
    print(f"[publish] ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def load_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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

    if any(fnmatch.fnmatch(rel_str, glob) for glob in DEFAULT_GLOB_EXCLUDES):
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


def copy_filtered(src_root: Path, dst_root: Path, patterns: list[str]) -> int:
    if dst_root.exists():
        shutil.rmtree(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)

    copied_files = 0
    for current_root, dirs, files in os.walk(src_root):
        rel_dir = Path(current_root).relative_to(src_root)
        if should_skip(rel_dir, patterns):
            dirs[:] = []
            continue

        dirs.sort()
        files.sort()

        dirs[:] = [d for d in dirs if not should_skip(rel_dir / d, patterns)]
        filtered_files = [f for f in files if not should_skip(rel_dir / f, patterns)]

        target_dir = dst_root / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        for file_name in filtered_files:
            rel_file = rel_dir / file_name
            src_path = src_root / rel_file
            dst_path = dst_root / rel_file
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            copied_files += 1

    return copied_files


def ensure_public_gitignore(dst_root: Path) -> None:
    path = dst_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    block = (
        "\n"
        "# --- AutoBlog: local-only (recommended) ---\n"
        "source/config.yaml\n"
        "public/\n"
    )

    if "source/config.yaml" in existing and "public/" in existing:
        return

    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(block)


def sanitize_example_config(dst_root: Path) -> None:
    """Make the example config safe and valid YAML (best-effort)."""
    example_path = dst_root / "source" / "config.yaml.example.yaml"
    if not example_path.exists():
        return

    text = example_path.read_text(encoding="utf-8")
    # Replace a common invalid YAML comment style used in the repo.
    # Specifically: api_key: "sk-..." //...
    lines: list[str] = []
    changed = False
    for line in text.splitlines():
        if "api_key:" in line and "sk-" in line and "//" in line:
            prefix = line.split("api_key:", 1)[0]
            lines.append(prefix + 'api_key: ""  # set via DEEPSEEK_API_KEY env var')
            changed = True
            continue
        if "//" in line:
            # Convert inline // comment into # comment (best-effort).
            left, right = line.split("//", 1)
            lines.append(left.rstrip() + "  #" + right)
            changed = True
            continue
        lines.append(line)

    if changed:
        example_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_remote_url(repo_root: Path, remote: str) -> str:
    res = run_git(["config", "--get", f"remote.{remote}.url"], cwd=repo_root)
    url = (res.stdout or "").strip() if res.returncode == 0 else ""
    if not url:
        die(f"Cannot resolve remote URL for '{remote}'.")
    return url


def remote_branch_exists(repo_root: Path, remote: str, branch: str) -> bool:
    url = get_remote_url(repo_root, remote)
    res = run_git(["ls-remote", "--heads", url, branch], cwd=repo_root)
    if res.returncode != 0:
        return False
    return bool((res.stdout or "").strip())


def main() -> None:
    args = parse_args()

    if args.exclude_file:
        exclude_path = (ROOT / args.exclude_file).resolve() if not os.path.isabs(args.exclude_file) else Path(args.exclude_file)
    else:
        exclude_path = next((p for p in DEFAULT_EXCLUDE_FILE_CANDIDATES if p.exists()), DEFAULT_EXCLUDE_FILE_CANDIDATES[0])

    patterns = load_patterns(exclude_path)
    remote_url = get_remote_url(ROOT, args.remote)

    if remote_branch_exists(ROOT, args.remote, args.branch) and not args.force:
        die(
            f"Remote branch '{args.branch}' already exists. "
            f"Re-run with --force to overwrite it."
        )

    with tempfile.TemporaryDirectory(prefix="autoblog-publish-") as tmp:
        tmp_dir = Path(tmp)
        snapshot_dir = tmp_dir / "snapshot"

        copied = copy_filtered(ROOT, snapshot_dir, patterns)
        if copied == 0:
            die("Snapshot is empty after applying exclude patterns.")

        ensure_public_gitignore(snapshot_dir)
        sanitize_example_config(snapshot_dir)

        # Initialize a fresh repo (no history).
        res = run_git(["init"], cwd=snapshot_dir)
        if res.returncode != 0:
            die(res.stderr.strip() or "git init failed")

        res = run_git(["add", "-A"], cwd=snapshot_dir)
        if res.returncode != 0:
            die(res.stderr.strip() or "git add failed")

        res = run_git(["commit", "-m", args.message], cwd=snapshot_dir)
        if res.returncode != 0:
            die(res.stderr.strip() or "git commit failed (check git user.name/email)")

        # Rename branch to requested name.
        res = run_git(["branch", "-M", args.branch], cwd=snapshot_dir)
        if res.returncode != 0:
            die(res.stderr.strip() or "git branch rename failed")

        res = run_git(["remote", "add", args.remote, remote_url], cwd=snapshot_dir)
        if res.returncode != 0:
            # Some git templates pre-create a default remote (e.g. "origin").
            # In that case, set/overwrite its URL instead of failing.
            res2 = run_git(["remote", "set-url", args.remote, remote_url], cwd=snapshot_dir)
            if res2.returncode != 0:
                die(res.stderr.strip() or res2.stderr.strip() or "git remote add failed")

        if args.dry_run:
            print(f"[publish] DRY RUN OK: prepared snapshot with {copied} files")
            print(f"[publish] Would push to {args.remote}:{args.branch} ({remote_url})")
            return

        push_args = ["push", args.remote, f"HEAD:refs/heads/{args.branch}"]
        if args.force:
            push_args.insert(1, "--force")
        res = run_git(push_args, cwd=snapshot_dir)
        if res.returncode != 0:
            die(res.stderr.strip() or "git push failed")

        print(f"[publish] OK: pushed sanitized snapshot to {args.remote}:{args.branch}")
        print(f"[publish] Exclude file: {exclude_path}")


if __name__ == "__main__":
    main()
