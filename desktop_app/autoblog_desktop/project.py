from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    root: Path

    @classmethod
    def detect(cls) -> "Project":
        # desktop_app/autoblog_desktop/* -> repo root is 2 levels up
        root = Path(__file__).resolve().parents[2]
        return cls(root=root)

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
    def config_path(self) -> Path:
        return self.source_dir / "config.yaml"

    @property
    def config_example_path(self) -> Path:
        return self.source_dir / "config.yaml.example.yaml"

    @property
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def assets_dir(self) -> Path:
        return self.source_dir / "assets"

    @property
    def public_dir(self) -> Path:
        return self.root / "public"
