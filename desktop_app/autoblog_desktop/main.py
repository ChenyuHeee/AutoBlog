from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
            "推荐使用“偏好设置”模式来配置站点（无需直接编辑 YAML）。\n"
            "如需自定义字段/保留注释，可切到“高级（YAML）”。"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.config_tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.config_tabs, 1)

        # --- Preferences (form) ---
        pref = QtWidgets.QWidget()
        pref_layout = QtWidgets.QVBoxLayout(pref)

        form_scroll = QtWidgets.QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        form_scroll.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        pref_layout.addWidget(form_scroll, 1)

        form_host = QtWidgets.QWidget()
        form_scroll.setWidget(form_host)
        form_layout = QtWidgets.QVBoxLayout(form_host)
        form_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(12)

        basic_group = QtWidgets.QGroupBox("基础")
        basic_form = QtWidgets.QFormLayout(basic_group)
        basic_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        basic_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.cfg_title = QtWidgets.QLineEdit()
        self.cfg_description = QtWidgets.QPlainTextEdit()
        self.cfg_description.setFixedHeight(80)
        self.cfg_timezone = QtWidgets.QLineEdit()
        self.cfg_author = QtWidgets.QLineEdit()
        self.cfg_site_url = QtWidgets.QLineEdit()
        self.cfg_base_url = QtWidgets.QLineEdit()
        self.cfg_rss_enabled = QtWidgets.QCheckBox("启用 RSS")
        basic_form.addRow("站点标题（title）", self.cfg_title)
        basic_form.addRow("站点描述（description）", self.cfg_description)
        basic_form.addRow("时区（timezone）", self.cfg_timezone)
        basic_form.addRow("作者（author）", self.cfg_author)
        basic_form.addRow("站点地址（site_url，可选）", self.cfg_site_url)
        basic_form.addRow("路径前缀（base_url，可选）", self.cfg_base_url)
        basic_form.addRow("", self.cfg_rss_enabled)
        form_layout.addWidget(basic_group)

        gh_group = QtWidgets.QGroupBox("GitHub Pages")
        gh_form = QtWidgets.QFormLayout(gh_group)
        gh_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        gh_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.cfg_github_repo = QtWidgets.QLineEdit()
        self.cfg_github_branch = QtWidgets.QLineEdit()
        self.cfg_github_remote = QtWidgets.QLineEdit()
        self.cfg_github_remote_url = QtWidgets.QLineEdit()
        gh_form.addRow("仓库（github_repo：owner/repo）", self.cfg_github_repo)
        gh_form.addRow("分支（github_branch，例如 gh-pages）", self.cfg_github_branch)
        gh_form.addRow("remote 名称（github_remote）", self.cfg_github_remote)
        gh_form.addRow("remote URL（github_remote_url，可选）", self.cfg_github_remote_url)
        form_layout.addWidget(gh_group)

        contacts_group = QtWidgets.QGroupBox("联系方式（contacts）")
        contacts_v = QtWidgets.QVBoxLayout(contacts_group)
        self.cfg_contacts = QtWidgets.QTableWidget(0, 4)
        self.cfg_contacts.setHorizontalHeaderLabels(["label", "url", "icon", "note"])
        self.cfg_contacts.horizontalHeader().setStretchLastSection(True)
        self.cfg_contacts.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.cfg_contacts.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.cfg_contacts.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.cfg_contacts.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.cfg_contacts.verticalHeader().setVisible(False)
        self.cfg_contacts.setAlternatingRowColors(True)
        self.cfg_contacts.setShowGrid(True)
        self.cfg_contacts.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cfg_contacts.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.SelectedClicked
            | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.cfg_contacts.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.cfg_contacts.setMinimumHeight(180)
        contacts_v.addWidget(self.cfg_contacts)

        contacts_btns = QtWidgets.QHBoxLayout()
        self.btn_contacts_add = QtWidgets.QPushButton("添加")
        self.btn_contacts_remove = QtWidgets.QPushButton("删除选中")
        contacts_btns.addWidget(self.btn_contacts_add)
        contacts_btns.addWidget(self.btn_contacts_remove)
        contacts_btns.addStretch(1)
        contacts_v.addLayout(contacts_btns)
        form_layout.addWidget(contacts_group)
        contacts_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

        music_group = QtWidgets.QGroupBox("背景音乐（background_music）")
        music_form = QtWidgets.QFormLayout(music_group)
        music_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        music_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.cfg_music_enabled = QtWidgets.QCheckBox("启用")
        self.cfg_music_src = QtWidgets.QLineEdit()
        self.cfg_music_title = QtWidgets.QLineEdit()
        self.cfg_music_artist = QtWidgets.QLineEdit()
        self.cfg_music_cover = QtWidgets.QLineEdit()
        self.cfg_music_autoplay = QtWidgets.QCheckBox("自动播放")
        self.cfg_music_start_muted = QtWidgets.QCheckBox("默认静音")
        music_form.addRow("", self.cfg_music_enabled)
        music_form.addRow("音频路径（src，基于 source/assets/）", self.cfg_music_src)
        music_form.addRow("标题（title）", self.cfg_music_title)
        music_form.addRow("歌手（artist）", self.cfg_music_artist)
        music_form.addRow("封面（cover）", self.cfg_music_cover)
        music_form.addRow("", self.cfg_music_autoplay)
        music_form.addRow("", self.cfg_music_start_muted)
        form_layout.addWidget(music_group)

        ai_group = QtWidgets.QGroupBox("AI 摘要（ai_summary）")
        ai_form = QtWidgets.QFormLayout(ai_group)
        ai_form.setLabelAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        ai_group.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.cfg_ai_provider = QtWidgets.QLineEdit()
        self.cfg_ai_api_key = QtWidgets.QLineEdit()
        self.cfg_ai_api_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.cfg_ai_model = QtWidgets.QLineEdit()
        self.cfg_ai_endpoint = QtWidgets.QLineEdit()
        self.cfg_ai_temperature = QtWidgets.QDoubleSpinBox()
        self.cfg_ai_temperature.setRange(0.0, 2.0)
        self.cfg_ai_temperature.setSingleStep(0.1)
        self.cfg_ai_temperature.setDecimals(2)
        self.cfg_ai_max_input_chars = QtWidgets.QSpinBox()
        self.cfg_ai_max_input_chars.setRange(0, 10_000_000)
        self.cfg_ai_max_tokens = QtWidgets.QSpinBox()
        self.cfg_ai_max_tokens.setRange(0, 10_000_000)
        self.cfg_ai_max_output_chars = QtWidgets.QSpinBox()
        self.cfg_ai_max_output_chars.setRange(0, 10_000_000)

        ai_form.addRow("provider", self.cfg_ai_provider)
        ai_form.addRow("api_key（建议用环境变量）", self.cfg_ai_api_key)
        ai_form.addRow("model", self.cfg_ai_model)
        ai_form.addRow("endpoint", self.cfg_ai_endpoint)
        ai_form.addRow("temperature", self.cfg_ai_temperature)
        ai_form.addRow("max_input_chars", self.cfg_ai_max_input_chars)
        ai_form.addRow("max_tokens", self.cfg_ai_max_tokens)
        ai_form.addRow("max_output_chars", self.cfg_ai_max_output_chars)
        form_layout.addWidget(ai_group)

        form_layout.addStretch(1)

        pref_btns = QtWidgets.QHBoxLayout()
        self.btn_pref_reload = QtWidgets.QPushButton("重新加载")
        self.btn_pref_save = QtWidgets.QPushButton("保存")
        pref_btns.addWidget(self.btn_pref_reload)
        pref_btns.addWidget(self.btn_pref_save)
        pref_btns.addStretch(1)
        pref_layout.addLayout(pref_btns)

        self.config_tabs.addTab(pref, "偏好设置")

        # --- Advanced YAML ---
        adv = QtWidgets.QWidget()
        adv_layout = QtWidgets.QVBoxLayout(adv)
        self.config_editor = QtWidgets.QPlainTextEdit()
        self.config_editor.setFont(self._mono_font())
        adv_layout.addWidget(self.config_editor, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_config_reload = QtWidgets.QPushButton("重新加载")
        self.btn_config_save = QtWidgets.QPushButton("保存")
        btn_row.addWidget(self.btn_config_reload)
        btn_row.addWidget(self.btn_config_save)
        btn_row.addStretch(1)
        adv_layout.addLayout(btn_row)

        self.config_tabs.addTab(adv, "高级（YAML）")

        # Wire events
        self.btn_config_reload.clicked.connect(self._config_reload)
        self.btn_config_save.clicked.connect(self._config_save)
        self.btn_pref_reload.clicked.connect(self._config_reload)
        self.btn_pref_save.clicked.connect(self._config_save_preferences)
        self.btn_contacts_add.clicked.connect(self._contacts_add_row)
        self.btn_contacts_remove.clicked.connect(self._contacts_remove_selected)

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
        self._load_preferences_from_yaml_text(content)
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
        self._load_preferences_from_yaml_text(content)
        self._toast("已保存 config.yaml")

    def _load_preferences_from_yaml_text(self, content: str) -> None:
        try:
            data = yaml.safe_load(content) or {}
        except Exception:
            return
        if not isinstance(data, dict):
            return
        self._prefs_set_from_dict(data)

    def _prefs_set_from_dict(self, data: dict[str, Any]) -> None:
        self.cfg_title.setText(str(data.get("title", "") or ""))
        self.cfg_description.setPlainText(str(data.get("description", "") or ""))
        self.cfg_timezone.setText(str(data.get("timezone", "") or ""))
        self.cfg_author.setText(str(data.get("author", "") or ""))
        self.cfg_site_url.setText(str(data.get("site_url", "") or ""))
        self.cfg_base_url.setText(str(data.get("base_url", "") or ""))

        rss_enabled = data.get("rss_enabled", True)
        self.cfg_rss_enabled.setChecked(bool(rss_enabled))

        self.cfg_github_repo.setText(str(data.get("github_repo", "") or ""))
        self.cfg_github_branch.setText(str(data.get("github_branch", "") or ""))
        self.cfg_github_remote.setText(str(data.get("github_remote", "") or ""))
        self.cfg_github_remote_url.setText(str(data.get("github_remote_url", "") or ""))

        # contacts
        self.cfg_contacts.setRowCount(0)
        contacts = data.get("contacts", [])
        if isinstance(contacts, list):
            for item in contacts:
                if not isinstance(item, dict):
                    continue
                self._contacts_add_row(
                    label=str(item.get("label", "") or ""),
                    url=str(item.get("url", "") or ""),
                    icon=str(item.get("icon", "") or ""),
                    note=str(item.get("note", "") or ""),
                )
        self._contacts_refresh_view()

        # background_music
        music = data.get("background_music", {})
        if not isinstance(music, dict):
            music = {}
        self.cfg_music_enabled.setChecked(bool(music.get("enabled", False)))
        self.cfg_music_src.setText(str(music.get("src", "") or ""))
        self.cfg_music_title.setText(str(music.get("title", "") or ""))
        self.cfg_music_artist.setText(str(music.get("artist", "") or ""))
        self.cfg_music_cover.setText(str(music.get("cover", "") or ""))
        self.cfg_music_autoplay.setChecked(bool(music.get("autoplay", False)))
        self.cfg_music_start_muted.setChecked(bool(music.get("start_muted", True)))

        # ai_summary
        ai = data.get("ai_summary", {})
        if not isinstance(ai, dict):
            ai = {}
        self.cfg_ai_provider.setText(str(ai.get("provider", "") or ""))
        self.cfg_ai_api_key.setText(str(ai.get("api_key", "") or ""))
        self.cfg_ai_model.setText(str(ai.get("model", "") or ""))
        self.cfg_ai_endpoint.setText(str(ai.get("endpoint", "") or ""))
        with contextlib.suppress(Exception):
            self.cfg_ai_temperature.setValue(float(ai.get("temperature", 0.2)))
        with contextlib.suppress(Exception):
            self.cfg_ai_max_input_chars.setValue(int(ai.get("max_input_chars", 6000)))
        with contextlib.suppress(Exception):
            self.cfg_ai_max_tokens.setValue(int(ai.get("max_tokens", 200)))
        with contextlib.suppress(Exception):
            self.cfg_ai_max_output_chars.setValue(int(ai.get("max_output_chars", 120)))

    def _prefs_collect_to_dict(self, base: dict[str, Any]) -> dict[str, Any]:
        data = dict(base)

        def set_if_non_empty(key: str, value: str) -> None:
            v = value.strip()
            if v:
                data[key] = v
            else:
                data.pop(key, None)

        set_if_non_empty("title", self.cfg_title.text())
        set_if_non_empty("description", self.cfg_description.toPlainText())
        set_if_non_empty("timezone", self.cfg_timezone.text())
        set_if_non_empty("author", self.cfg_author.text())
        set_if_non_empty("site_url", self.cfg_site_url.text())
        set_if_non_empty("base_url", self.cfg_base_url.text())

        # Keep rss_enabled explicit for clarity.
        data["rss_enabled"] = bool(self.cfg_rss_enabled.isChecked())

        set_if_non_empty("github_repo", self.cfg_github_repo.text())
        set_if_non_empty("github_branch", self.cfg_github_branch.text())
        set_if_non_empty("github_remote", self.cfg_github_remote.text())
        set_if_non_empty("github_remote_url", self.cfg_github_remote_url.text())

        # contacts
        contacts: list[dict[str, str]] = []
        for row in range(self.cfg_contacts.rowCount()):
            def item_text(col: int) -> str:
                it = self.cfg_contacts.item(row, col)
                return (it.text() if it else "").strip()

            label = item_text(0)
            url = item_text(1)
            icon = item_text(2)
            note = item_text(3)
            if not any([label, url, icon, note]):
                continue
            item: dict[str, str] = {}
            if label:
                item["label"] = label
            if url:
                item["url"] = url
            if icon:
                item["icon"] = icon
            if note:
                item["note"] = note
            contacts.append(item)
        if contacts:
            data["contacts"] = contacts
        else:
            data.pop("contacts", None)

        # background_music
        music: dict[str, Any] = {}
        if self.cfg_music_enabled.isChecked():
            music["enabled"] = True
            if self.cfg_music_src.text().strip():
                music["src"] = self.cfg_music_src.text().strip()
            if self.cfg_music_title.text().strip():
                music["title"] = self.cfg_music_title.text().strip()
            if self.cfg_music_artist.text().strip():
                music["artist"] = self.cfg_music_artist.text().strip()
            if self.cfg_music_cover.text().strip():
                music["cover"] = self.cfg_music_cover.text().strip()
            music["autoplay"] = bool(self.cfg_music_autoplay.isChecked())
            music["start_muted"] = bool(self.cfg_music_start_muted.isChecked())
            data["background_music"] = music
        else:
            data.pop("background_music", None)

        # ai_summary
        ai: dict[str, Any] = {}
        if self.cfg_ai_provider.text().strip() or self.cfg_ai_model.text().strip() or self.cfg_ai_endpoint.text().strip():
            if self.cfg_ai_provider.text().strip():
                ai["provider"] = self.cfg_ai_provider.text().strip()
            if self.cfg_ai_api_key.text().strip():
                ai["api_key"] = self.cfg_ai_api_key.text().strip()
            if self.cfg_ai_model.text().strip():
                ai["model"] = self.cfg_ai_model.text().strip()
            if self.cfg_ai_endpoint.text().strip():
                ai["endpoint"] = self.cfg_ai_endpoint.text().strip()
            ai["temperature"] = float(self.cfg_ai_temperature.value())
            ai["max_input_chars"] = int(self.cfg_ai_max_input_chars.value())
            ai["max_tokens"] = int(self.cfg_ai_max_tokens.value())
            ai["max_output_chars"] = int(self.cfg_ai_max_output_chars.value())
            data["ai_summary"] = ai
        else:
            data.pop("ai_summary", None)

        return data

    def _config_save_preferences(self) -> None:
        # Merge preference values into existing YAML dict, to preserve unknown keys.
        raw = self.config_editor.toPlainText()
        try:
            base = yaml.safe_load(raw) or {}
        except Exception:
            base = {}
        if not isinstance(base, dict):
            base = {}

        data = self._prefs_collect_to_dict(base)
        yaml_text = yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

        write_text(self.project.config_path, yaml_text if yaml_text.endswith("\n") else yaml_text + "\n")
        self.config_editor.setPlainText(yaml_text)
        self._toast("已保存 config.yaml（偏好设置）")

    def _contacts_add_row(self, *, label: str = "", url: str = "", icon: str = "", note: str = "") -> None:
        row = self.cfg_contacts.rowCount()
        self.cfg_contacts.insertRow(row)
        for col, value in enumerate([label, url, icon, note]):
            item = QtWidgets.QTableWidgetItem(value)
            self.cfg_contacts.setItem(row, col, item)
        self._contacts_refresh_view()

    def _contacts_remove_selected(self) -> None:
        selected = self.cfg_contacts.selectionModel().selectedRows()
        rows = sorted((idx.row() for idx in selected), reverse=True)
        for r in rows:
            self.cfg_contacts.removeRow(r)
        self._contacts_refresh_view()

    def _contacts_refresh_view(self) -> None:
        # Ensure the table is readable even inside a scroll area.
        with contextlib.suppress(Exception):
            self.cfg_contacts.resizeColumnsToContents()
        with contextlib.suppress(Exception):
            self.cfg_contacts.resizeRowsToContents()

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
