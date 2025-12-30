from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml
from PySide6 import QtCore, QtGui, QtWidgets

from .fs import list_files, read_text, write_text
from .preview_server import PreviewServer
from .project import Project


def _ensure_repo_on_syspath(project_root: Path) -> None:
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


@dataclass
class CurrentFile:
    path: Path | None = None


class BuildWorker(QtCore.QThread):
    finished_ok = QtCore.Signal(str)
    finished_err = QtCore.Signal(str)

    def __init__(self, project_root: Path, *, include_drafts: bool, skip_clean: bool):
        super().__init__()
        self.project_root = project_root
        self.include_drafts = include_drafts
        self.skip_clean = skip_clean

    def run(self) -> None:
        try:
            _ensure_repo_on_syspath(self.project_root)
            import build as autoblog_build

            args = argparse.Namespace(
                skip_clean=self.skip_clean,
                drafts=self.include_drafts,
                deploy=False,
                remote=None,
                branch=None,
                dry_run=True,
                message=None,
            )

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                autoblog_build.build_site(args)

            self.finished_ok.emit(buf.getvalue())
        except Exception as exc:
            self.finished_err.emit(str(exc))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.current = CurrentFile()
        self.preview_server: PreviewServer | None = None
        self.build_worker: BuildWorker | None = None

        self.setWindowTitle("AutoBlog Desktop")
        self.resize(1280, 780)

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self._init_config_tab()
        self._init_content_tab()
        self._init_theme_tab()
        self._init_build_tab()

        self.statusBar().showMessage(f"Project: {self.project.root}")

    # -------------------- Tabs --------------------

    def _init_config_tab(self) -> None:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        info = QtWidgets.QLabel(
            "编辑 source/config.yaml（保存前会做 YAML 校验）。建议配合 Git 使用。"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.config_editor = QtWidgets.QPlainTextEdit()
        self.config_editor.setFont(self._mono_font())
        layout.addWidget(self.config_editor, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_config_reload = QtWidgets.QPushButton("重新加载")
        self.btn_config_save = QtWidgets.QPushButton("保存")
        btn_row.addWidget(self.btn_config_reload)
        btn_row.addWidget(self.btn_config_save)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.btn_config_reload.clicked.connect(self._config_reload)
        self.btn_config_save.clicked.connect(self._config_save)

        self.tabs.addTab(tab, "Config")
        self._config_reload()

    def _init_content_tab(self) -> None:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.content_list = QtWidgets.QListWidget()
        left_layout.addWidget(self.content_list, 1)

        self.btn_content_refresh = QtWidgets.QPushButton("刷新列表")
        left_layout.addWidget(self.btn_content_refresh)
        splitter.addWidget(left)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.file_label = QtWidgets.QLabel("未选择文件")
        self.file_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.file_label)

        inner = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        right_layout.addWidget(inner, 1)

        self.file_editor = QtWidgets.QPlainTextEdit()
        self.file_editor.setFont(self._mono_font())
        inner.addWidget(self.file_editor)

        self.preview = QtWidgets.QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        inner.addWidget(self.preview)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_file_save = QtWidgets.QPushButton("保存")
        self.btn_open_in_finder = QtWidgets.QPushButton("在 Finder 中打开")
        btn_row.addWidget(self.btn_file_save)
        btn_row.addWidget(self.btn_open_in_finder)
        btn_row.addStretch(1)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.tabs.addTab(tab, "内容")

        self.btn_content_refresh.clicked.connect(self._refresh_content_list)
        self.content_list.currentTextChanged.connect(self._open_relative_path)
        self.btn_file_save.clicked.connect(self._save_current_file)
        self.btn_open_in_finder.clicked.connect(self._reveal_current_file)

        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self.file_editor.textChanged.connect(self._schedule_preview)

        self._refresh_content_list()

    def _init_theme_tab(self) -> None:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.addWidget(QtWidgets.QLabel("选择 templates/ 或 source/assets/ 文件进行编辑（与内容编辑器共用）。"))

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        self.theme_list = QtWidgets.QListWidget()
        splitter.addWidget(self.theme_list)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.theme_hint = QtWidgets.QLabel("从左侧选择文件")
        right_layout.addWidget(self.theme_hint)

        self.theme_editor = QtWidgets.QPlainTextEdit()
        self.theme_editor.setFont(self._mono_font())
        right_layout.addWidget(self.theme_editor, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_theme_save = QtWidgets.QPushButton("保存")
        self.btn_theme_refresh = QtWidgets.QPushButton("刷新列表")
        btn_row.addWidget(self.btn_theme_save)
        btn_row.addWidget(self.btn_theme_refresh)
        btn_row.addStretch(1)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)

        self.tabs.addTab(tab, "主题")

        self.theme_list.currentTextChanged.connect(self._open_theme_relative_path)
        self.btn_theme_save.clicked.connect(self._save_theme_file)
        self.btn_theme_refresh.clicked.connect(self._refresh_theme_list)

        self._refresh_theme_list()

    def _init_build_tab(self) -> None:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        row = QtWidgets.QHBoxLayout()
        self.chk_drafts = QtWidgets.QCheckBox("包含 draft")
        self.chk_skip_clean = QtWidgets.QCheckBox("跳过清理 public/")
        self.btn_build = QtWidgets.QPushButton("构建")
        self.btn_start_preview = QtWidgets.QPushButton("启动预览服务")
        self.btn_open_preview = QtWidgets.QPushButton("打开预览")
        self.btn_open_preview.setEnabled(False)

        row.addWidget(self.chk_drafts)
        row.addWidget(self.chk_skip_clean)
        row.addWidget(self.btn_build)
        row.addSpacing(14)
        row.addWidget(self.btn_start_preview)
        row.addWidget(self.btn_open_preview)
        row.addStretch(1)
        layout.addLayout(row)

        self.build_log = QtWidgets.QPlainTextEdit()
        self.build_log.setReadOnly(True)
        self.build_log.setFont(self._mono_font())
        layout.addWidget(self.build_log, 1)

        self.tabs.addTab(tab, "构建/预览")

        self.btn_build.clicked.connect(self._run_build)
        self.btn_start_preview.clicked.connect(self._ensure_preview_server)
        self.btn_open_preview.clicked.connect(self._open_preview_url)

    # -------------------- Helpers --------------------

    def _mono_font(self) -> QtGui.QFont:
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(12)
        return font

    def _toast(self, text: str) -> None:
        self.statusBar().showMessage(text, 5000)

    # -------------------- Config --------------------

    def _config_reload(self) -> None:
        path = self.project.config_path
        content = read_text(path)
        if not content:
            content = read_text(self.project.config_example_path)
        self.config_editor.setPlainText(content)
        self._toast("Config 已加载")

    def _config_save(self) -> None:
        content = self.config_editor.toPlainText()
        try:
            parsed = yaml.safe_load(content) or {}
            if not isinstance(parsed, dict):
                raise ValueError("config.yaml 必须是 YAML 字典（mapping）")
        except Exception as exc:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setWindowTitle("YAML 错误")
            msg.setText(str(exc))
            msg.exec()
            return

        write_text(self.project.config_path, content if content.endswith("\n") else content + "\n")
        self._toast("已保存 config.yaml")

    # -------------------- Content editor --------------------

    def _refresh_content_list(self) -> None:
        files = []
        for p in list_files(self.project.posts_dir, include_globs=("**/*.md",)):
            files.append(p.relative_to(self.project.root).as_posix())
        for p in list_files(self.project.pages_dir, include_globs=("**/*.md",)):
            files.append(p.relative_to(self.project.root).as_posix())
        files.sort(key=str.lower)

        self.content_list.blockSignals(True)
        self.content_list.clear()
        self.content_list.addItems(files)
        self.content_list.blockSignals(False)
        self._toast(f"已加载 {len(files)} 个 Markdown 文件")

    def _open_relative_path(self, rel: str) -> None:
        if not rel:
            return
        path = (self.project.root / rel).resolve()
        if not path.exists() or not path.is_file():
            return
        self.current.path = path
        self.file_label.setText(rel)
        self.file_editor.blockSignals(True)
        self.file_editor.setPlainText(read_text(path))
        self.file_editor.blockSignals(False)
        self._render_preview_now()

    def _schedule_preview(self) -> None:
        if self.current.path is None:
            return
        if self.current.path.suffix.lower() != ".md":
            return
        self._preview_timer.start()

    def _render_preview_now(self) -> None:
        if self.current.path is None:
            self.preview.setHtml("<p>未选择文件</p>")
            return
        if self.current.path.suffix.lower() != ".md":
            self.preview.setHtml("<p>当前文件不是 Markdown，不提供预览。</p>")
            return

        try:
            _ensure_repo_on_syspath(self.project.root)
            import build as autoblog_build

            raw = self.file_editor.toPlainText()
            _, body = autoblog_build.extract_front_matter(raw)
            html = autoblog_build.render_markdown(body)
            self.preview.setHtml(html)
        except Exception as exc:
            self.preview.setHtml(f"<pre>预览失败：{exc}</pre>")

    def _save_current_file(self) -> None:
        if self.current.path is None:
            return
        write_text(self.current.path, self.file_editor.toPlainText())
        self._toast("已保存")

    def _reveal_current_file(self) -> None:
        if self.current.path is None:
            return
        url = QtCore.QUrl.fromLocalFile(str(self.current.path))
        QtGui.QDesktopServices.openUrl(url)

    # -------------------- Theme editor --------------------

    def _refresh_theme_list(self) -> None:
        files: list[str] = []
        for p in list_files(self.project.templates_dir, include_globs=("**/*.html",)):
            files.append(p.relative_to(self.project.root).as_posix())
        for p in list_files(self.project.assets_dir, include_globs=("**/*.css", "**/*.js")):
            files.append(p.relative_to(self.project.root).as_posix())
        files.sort(key=str.lower)

        self.theme_list.blockSignals(True)
        self.theme_list.clear()
        self.theme_list.addItems(files)
        self.theme_list.blockSignals(False)
        self._toast(f"已加载 {len(files)} 个主题文件")

    def _open_theme_relative_path(self, rel: str) -> None:
        if not rel:
            return
        path = (self.project.root / rel).resolve()
        if not path.exists() or not path.is_file():
            return
        self._theme_current = path
        self.theme_hint.setText(rel)
        self.theme_editor.setPlainText(read_text(path))

    def _save_theme_file(self) -> None:
        path = getattr(self, "_theme_current", None)
        if not path:
            return
        write_text(path, self.theme_editor.toPlainText())
        self._toast("已保存主题文件")

    # -------------------- Build & Preview --------------------

    def _append_log(self, text: str) -> None:
        if not text:
            return
        self.build_log.appendPlainText(text.rstrip())

    def _run_build(self) -> None:
        if self.build_worker is not None and self.build_worker.isRunning():
            return

        include_drafts = self.chk_drafts.isChecked()
        skip_clean = self.chk_skip_clean.isChecked()

        self._append_log("\n=== Build: {} ===".format(dt.datetime.now().isoformat(timespec="seconds")))
        self._append_log(f"include_drafts={include_drafts} skip_clean={skip_clean}")

        self.build_worker = BuildWorker(self.project.root, include_drafts=include_drafts, skip_clean=skip_clean)
        self.build_worker.finished_ok.connect(self._on_build_ok)
        self.build_worker.finished_err.connect(self._on_build_err)
        self.build_worker.start()

    def _on_build_ok(self, output: str) -> None:
        self._append_log(output or "(no output)")
        self._toast("构建完成")

    def _on_build_err(self, err: str) -> None:
        self._append_log(f"[ERROR] {err}")
        msg = QtWidgets.QMessageBox(self)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        msg.setWindowTitle("构建失败")
        msg.setText(err)
        msg.exec()

    def _ensure_preview_server(self) -> None:
        if self.preview_server is None:
            self.preview_server = PreviewServer(self.project.public_dir)
            self.preview_server.start()
            self._append_log(f"Preview server: {self.preview_server.url}")
            self.btn_open_preview.setEnabled(True)
            self._toast("预览服务已启动")

    def _open_preview_url(self) -> None:
        self._ensure_preview_server()
        if not self.preview_server:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.preview_server.url))


def run() -> int:
    app = QtWidgets.QApplication(sys.argv)
    project = Project.detect()
    window = MainWindow(project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
