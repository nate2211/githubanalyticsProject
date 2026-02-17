# gui.py
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont, QDesktopServices, QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QMessageBox, QFileDialog, QGroupBox, QFormLayout,
    QCheckBox, QPlainTextEdit, QSplitter, QHeaderView, QAbstractItemView,
    QComboBox, QInputDialog, QMenuBar, QAction
)

from blocks import BLOCKS, app_dir, load_json, save_json


# ----------------- block runner -----------------

def run_block(name: str, payload: Any, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, Dict[str, Any]]:
    blk_cls = BLOCKS.get(name)
    blk = blk_cls()
    return blk.execute(payload, params=params or {})


# ----------------- theme -----------------

def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(25, 25, 28))
    pal.setColor(QPalette.WindowText, QColor(235, 235, 235))
    pal.setColor(QPalette.Base, QColor(18, 18, 20))
    pal.setColor(QPalette.AlternateBase, QColor(28, 28, 32))
    pal.setColor(QPalette.ToolTipBase, QColor(235, 235, 235))
    pal.setColor(QPalette.ToolTipText, QColor(25, 25, 28))
    pal.setColor(QPalette.Text, QColor(235, 235, 235))
    pal.setColor(QPalette.Button, QColor(33, 33, 38))
    pal.setColor(QPalette.ButtonText, QColor(235, 235, 235))
    pal.setColor(QPalette.BrightText, QColor(255, 60, 60))
    pal.setColor(QPalette.Highlight, QColor(70, 110, 200))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.Link, QColor(120, 170, 255))
    app.setPalette(pal)

    app.setStyleSheet("""
        QGroupBox { font-weight: 600; }
        QHeaderView::section {
            padding: 6px;
            border: 0px;
            background: #2b2b30;
            color: #eaeaea;
        }
        QTableWidget { gridline-color: #3a3a42; }
        QPlainTextEdit, QLineEdit {
            border: 1px solid #3a3a42;
            border-radius: 6px;
            padding: 6px;
        }
        QComboBox {
            border: 1px solid #3a3a42;
            border-radius: 6px;
            padding: 4px 8px;
            background: #18181a;
        }
        QPushButton {
            padding: 7px 10px;
            border-radius: 8px;
            border: 1px solid #3a3a42;
            background: #2a2a30;
        }
        QPushButton:hover { background: #32323a; }
        QPushButton:pressed { background: #24242a; }
        QTabWidget::pane { border: 1px solid #3a3a42; }
    """)


# ----------------- Main Window -----------------

class MainWindow(QMainWindow):
    COLS = [
        "Repo",
        "Commits",
        "Stars",
        "Forks",
        "Watchers",
        "Open Issues",
        "Release DL Total",
        "Views (14d)",
        "Views Unique",
        "Clones (14d)",
        "Clones Unique",
        "Traffic OK",
    ]

    DEFAULT_PRESET_NAME = "Default"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nate's GitHub Analytics Project")
        self.setMinimumSize(1120, 740)

        self.cfg_path = app_dir() / "config.json"
        self.cfg = self._load_cfg()

        self.last_data: Dict[str, Any] = {}

        self._build_menu()

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Split: Settings (top) / Results (bottom)
        outer = QSplitter(Qt.Vertical)
        root_layout.addWidget(outer, 1)

        # ---------------- Settings ----------------
        settings = QWidget()
        s_lay = QVBoxLayout(settings)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(10)

        # Presets bar
        presets_box = QGroupBox("Presets")
        presets_form = QFormLayout(presets_box)

        row = QWidget()
        row_l = QHBoxLayout(row)
        row_l.setContentsMargins(0, 0, 0, 0)

        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(260)

        self.btn_apply_preset = QPushButton("Apply")
        self.btn_save_as_preset = QPushButton("Save As…")
        self.btn_update_preset = QPushButton("Update")
        self.btn_rename_preset = QPushButton("Rename…")
        self.btn_delete_preset = QPushButton("Delete")

        row_l.addWidget(self.preset_combo, 1)
        row_l.addWidget(self.btn_apply_preset)
        row_l.addWidget(self.btn_save_as_preset)
        row_l.addWidget(self.btn_update_preset)
        row_l.addWidget(self.btn_rename_preset)
        row_l.addWidget(self.btn_delete_preset)

        presets_form.addRow("Preset:", row)
        s_lay.addWidget(presets_box)

        # Settings box
        box = QGroupBox("Settings")
        form = QFormLayout(box)

        self.repos_edit = QPlainTextEdit()
        self.repos_edit.setPlaceholderText("One repo per line. Format: owner/name or https://github.com/owner/name")
        self.repos_edit.setMinimumHeight(120)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText(
            "GitHub token (optional). Needed for traffic endpoints (views/clones/referrers/paths)."
        )

        self.remember_cb = QCheckBox("Remember token in config.json (NOT recommended)")
        self.remember_cb.setChecked(bool(self.cfg.get("remember_token")))

        help_lbl = QLabel("Note: Traffic (views/clones) is always the last 14 days on GitHub.")
        help_lbl.setStyleSheet("color: #bdbdbd;")

        form.addRow("Repos:", self.repos_edit)
        form.addRow("Token:", self.token_edit)
        form.addRow("", self.remember_cb)
        form.addRow("", help_lbl)

        s_lay.addWidget(box)

        # Buttons
        btn_row = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch analytics")
        self.export_btn = QPushButton("Export JSON…")
        self.load_btn = QPushButton("Load config…")
        self.save_btn = QPushButton("Save config")
        self.autofit_btn = QPushButton("Auto-fit columns")
        btn_row.addWidget(self.fetch_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.autofit_btn)
        s_lay.addLayout(btn_row)

        self.totals_label = QLabel("")
        self.totals_label.setAlignment(Qt.AlignLeft)
        s_lay.addWidget(self.totals_label)

        outer.addWidget(settings)

        # ---------------- Results ----------------
        results = QSplitter(Qt.Vertical)
        outer.addWidget(results)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)

        table_font = QFont()
        table_font.setPointSize(10)
        self.table.setFont(table_font)

        hdr = self.table.horizontalHeader()
        hdr.setSectionsMovable(True)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(True)
        hdr.setMinimumSectionSize(70)

        vhd = self.table.verticalHeader()
        vhd.setDefaultSectionSize(26)

        results.addWidget(self.table)

        self.tabs = QTabWidget()
        results.addWidget(self.tabs)

        mono = QFont("Consolas")
        mono.setStyleHint(QFont.Monospace)
        mono.setPointSize(10)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(mono)
        self.tabs.addTab(self.details, "Details (raw JSON)")

        self.errors = QPlainTextEdit()
        self.errors.setReadOnly(True)
        self.errors.setFont(mono)
        self.tabs.addTab(self.errors, "Errors / Warnings")

        # Stretch: results bigger
        outer.setStretchFactor(0, 0)
        outer.setStretchFactor(1, 1)
        results.setStretchFactor(0, 2)
        results.setStretchFactor(1, 1)

        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # signals
        self.fetch_btn.clicked.connect(self.on_fetch)
        self.export_btn.clicked.connect(self.on_export)
        self.load_btn.clicked.connect(self.on_load_cfg)
        self.save_btn.clicked.connect(self.on_save_cfg)
        self.autofit_btn.clicked.connect(self.on_autofit)
        self.table.itemDoubleClicked.connect(self.on_open_repo)

        self.btn_apply_preset.clicked.connect(self.on_apply_preset)
        self.btn_save_as_preset.clicked.connect(self.on_save_as_preset)
        self.btn_update_preset.clicked.connect(self.on_update_preset)
        self.btn_rename_preset.clicked.connect(self.on_rename_preset)
        self.btn_delete_preset.clicked.connect(self.on_delete_preset)

        # init ui from cfg
        self._load_cfg_to_ui()
        self.on_autofit()

    # ---------------- config + presets ----------------

    def _load_cfg(self) -> Dict[str, Any]:
        default_repos = [
            "nate2211/MelodyProject",
            "nate2211/GraphicsProject",
            "nate2211/AudioProject",
            "nate2211/VideoProject",
        ]
        cfg = load_json(self.cfg_path, default={})
        if not isinstance(cfg, dict):
            cfg = {}

        presets = cfg.get("presets")
        if not isinstance(presets, dict) or not presets:
            presets = {self.DEFAULT_PRESET_NAME: default_repos}
        else:
            # sanitize to list[str]
            clean: Dict[str, List[str]] = {}
            for k, v in presets.items():
                if not k or not isinstance(k, str):
                    continue
                if isinstance(v, list):
                    clean[k] = [str(x).strip() for x in v if str(x).strip()]
            presets = clean or {self.DEFAULT_PRESET_NAME: default_repos}

        active = cfg.get("active_preset")
        if not isinstance(active, str) or active not in presets:
            active = self.DEFAULT_PRESET_NAME if self.DEFAULT_PRESET_NAME in presets else sorted(presets.keys())[0]

        # keep compatibility: cfg["repos"] mirrors the active preset
        cfg_out = {
            "token": str(cfg.get("token") or ""),
            "remember_token": bool(cfg.get("remember_token")),
            "presets": presets,
            "active_preset": active,
            "repos": presets.get(active, default_repos),
        }
        return cfg_out

    def _save_cfg(self) -> None:
        # keep cfg["repos"] in sync with active preset contents
        active = str(self.cfg.get("active_preset") or "")
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if active and isinstance(presets, dict) and active in presets:
            self.cfg["repos"] = presets.get(active, [])
        save_json(self.cfg_path, self.cfg)

    def _current_repos_from_ui(self) -> List[str]:
        repos_lines = [ln.strip() for ln in self.repos_edit.toPlainText().splitlines()]
        return [ln for ln in repos_lines if ln]

    def _refresh_preset_combo(self) -> None:
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        active = str(self.cfg.get("active_preset") or "")

        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in sorted(presets.keys(), key=lambda s: s.lower()):
            self.preset_combo.addItem(name)
        # select active
        idx = self.preset_combo.findText(active)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def _load_cfg_to_ui(self) -> None:
        self._refresh_preset_combo()

        # token behavior: env var wins for display
        env_tok = (os.environ.get("GITHUB_TOKEN") or "").strip()
        tok = env_tok or (self.cfg.get("token") or "")
        self.token_edit.setText(tok if tok else "")
        self.remember_cb.setChecked(bool(self.cfg.get("remember_token")))

        # show active preset repos in editor
        active = str(self.cfg.get("active_preset") or "")
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        repos = presets.get(active, [])
        self.repos_edit.setPlainText("\n".join(str(x) for x in repos))

    def _ui_to_cfg_settings_only(self) -> None:
        token = self.token_edit.text().strip()
        remember = bool(self.remember_cb.isChecked())
        self.cfg["remember_token"] = remember
        self.cfg["token"] = token if remember else ""

    # ---------------- menu ----------------

    def _build_menu(self) -> None:
        menubar = QMenuBar(self)

        file_menu = menubar.addMenu("&File")
        act_load = QAction("Load config…", self)
        act_save = QAction("Save config", self)
        act_export = QAction("Export JSON…", self)
        act_quit = QAction("Quit", self)

        act_load.triggered.connect(self.on_load_cfg)
        act_save.triggered.connect(self.on_save_cfg)
        act_export.triggered.connect(self.on_export)
        act_quit.triggered.connect(self.close)

        file_menu.addAction(act_load)
        file_menu.addAction(act_save)
        file_menu.addSeparator()
        file_menu.addAction(act_export)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        presets_menu = menubar.addMenu("&Presets")
        act_apply = QAction("Apply selected preset", self)
        act_save_as = QAction("Save current as…", self)
        act_update = QAction("Update selected", self)
        act_rename = QAction("Rename selected…", self)
        act_delete = QAction("Delete selected", self)

        act_apply.triggered.connect(self.on_apply_preset)
        act_save_as.triggered.connect(self.on_save_as_preset)
        act_update.triggered.connect(self.on_update_preset)
        act_rename.triggered.connect(self.on_rename_preset)
        act_delete.triggered.connect(self.on_delete_preset)

        presets_menu.addAction(act_apply)
        presets_menu.addAction(act_save_as)
        presets_menu.addAction(act_update)
        presets_menu.addAction(act_rename)
        presets_menu.addAction(act_delete)

        view_menu = menubar.addMenu("&View")
        act_autofit = QAction("Auto-fit columns", self)
        act_autofit.triggered.connect(self.on_autofit)
        view_menu.addAction(act_autofit)

        self.setMenuBar(menubar)

    # ---------------- preset actions ----------------

    def _selected_preset_name(self) -> str:
        return str(self.preset_combo.currentText() or "").strip()

    def on_apply_preset(self) -> None:
        name = self._selected_preset_name()
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        repos = presets.get(name)
        if not isinstance(repos, list):
            return
        self.cfg["active_preset"] = name
        self.repos_edit.setPlainText("\n".join(str(x) for x in repos))
        self._save_cfg()
        self.status.showMessage(f"Applied preset: {name}")

    def on_save_as_preset(self) -> None:
        repos = self._current_repos_from_ui()
        if not repos:
            QMessageBox.information(self, "No repos", "Add at least one repo before saving a preset.")
            return

        name, ok = QInputDialog.getText(self, "Save Preset As…", "Preset name:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return

        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if name in presets:
            res = QMessageBox.question(
                self,
                "Overwrite?",
                f"Preset '{name}' already exists.\nOverwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        presets[name] = repos
        self.cfg["presets"] = presets
        self.cfg["active_preset"] = name
        self._ui_to_cfg_settings_only()
        self._save_cfg()
        self._refresh_preset_combo()
        self.status.showMessage(f"Saved preset: {name}")

    def on_update_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            return
        repos = self._current_repos_from_ui()
        if not repos:
            QMessageBox.information(self, "No repos", "Add at least one repo before updating a preset.")
            return

        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if name not in presets:
            QMessageBox.information(self, "Missing preset", "That preset no longer exists.")
            return

        presets[name] = repos
        self.cfg["presets"] = presets
        self.cfg["active_preset"] = name
        self._ui_to_cfg_settings_only()
        self._save_cfg()
        self.status.showMessage(f"Updated preset: {name}")

    def on_rename_preset(self) -> None:
        old = self._selected_preset_name()
        if not old:
            return
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if old not in presets:
            return

        new, ok = QInputDialog.getText(self, "Rename Preset…", "New name:", text=old)
        if not ok:
            return
        new = (new or "").strip()
        if not new or new == old:
            return
        if new in presets:
            QMessageBox.information(self, "Name exists", "A preset with that name already exists.")
            return

        presets[new] = presets.pop(old)
        self.cfg["presets"] = presets
        if self.cfg.get("active_preset") == old:
            self.cfg["active_preset"] = new
        self._save_cfg()
        self._refresh_preset_combo()
        self.status.showMessage(f"Renamed preset: {old} → {new}")

    def on_delete_preset(self) -> None:
        name = self._selected_preset_name()
        if not name:
            return
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if name not in presets:
            return

        if len(presets.keys()) <= 1:
            QMessageBox.information(self, "Can't delete", "You must keep at least one preset.")
            return

        res = QMessageBox.question(
            self,
            "Delete preset?",
            f"Delete preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return

        presets.pop(name, None)
        self.cfg["presets"] = presets

        # pick new active if needed
        if self.cfg.get("active_preset") == name:
            self.cfg["active_preset"] = sorted(presets.keys())[0]

        self._save_cfg()
        self._refresh_preset_combo()
        self.on_apply_preset()
        self.status.showMessage(f"Deleted preset: {name}")

    # ---------------- config buttons ----------------

    def on_save_cfg(self) -> None:
        # write current editor repos into the active preset before saving
        active = str(self.cfg.get("active_preset") or "")
        presets = self.cfg.get("presets") if isinstance(self.cfg.get("presets"), dict) else {}
        if active:
            presets[active] = self._current_repos_from_ui()
            self.cfg["presets"] = presets
        self._ui_to_cfg_settings_only()
        self._save_cfg()
        QMessageBox.information(self, "Saved", f"Saved config:\n{self.cfg_path}")

    def on_load_cfg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load config.json", str(app_dir()), "JSON (*.json)")
        if not path:
            return
        try:
            # load as raw then normalize through _load_cfg() logic by swapping cfg_path temporarily
            old_path = self.cfg_path
            self.cfg_path = Path(path)
            self.cfg = self._load_cfg()
            self.cfg_path = old_path  # keep writing to app default path
            self._save_cfg()          # persist normalized loaded config into default location
            self._load_cfg_to_ui()
            QMessageBox.information(self, "Loaded", f"Loaded presets/config and saved into:\n{old_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ---------------- fetching + rendering ----------------

    def on_fetch(self) -> None:
        # always fetch from the editor contents (so you can tweak without saving a preset)
        repos = self._current_repos_from_ui()
        token = self.token_edit.text().strip()
        payload = {"repos": repos, "token": token}

        self.errors.setPlainText("")
        self.details.setPlainText("")
        self.table.setRowCount(0)
        self.totals_label.setText("Fetching…")
        self.status.showMessage("Fetching analytics…")

        try:
            data, _m1 = run_block("github_fetch", payload, {})
            data, _m2 = run_block("github_aggregate", data, {})
            self.last_data = data if isinstance(data, dict) else {}
            self._render(self.last_data)
            self.status.showMessage("Done")
        except Exception as e:
            self.totals_label.setText("")
            self.status.showMessage("Fetch failed")
            QMessageBox.critical(self, "Fetch failed", str(e))

    def _render(self, data: Dict[str, Any]) -> None:
        repos = data.get("repos") or []
        errs = data.get("errors") or []
        totals = data.get("totals") or {}

        # 1. LOCK THE TABLE
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)  # Clear it out first
        self.table.setRowCount(len(repos))

        warnings: List[str] = []

        for i, r in enumerate(repos):
            if not isinstance(r, dict):
                continue

            repo_name = str(r.get("repo") or "")
            html_url = str(r.get("html_url") or "")

            commits = int(r.get("commits_total") or 0)
            stars = int(r.get("stars") or 0)
            forks = int(r.get("forks") or 0)
            watchers = int(r.get("watchers") or 0)
            issues = int(r.get("open_issues") or 0)
            rdl = int(r.get("release_asset_downloads_total") or 0)

            traffic = r.get("traffic") if isinstance(r.get("traffic"), dict) else {}
            traffic_err = str(r.get("traffic_error") or "").strip()

            # ✅ per-repo traffic counts come from the traffic endpoint response
            views_total = views_unique = clones_total = clones_unique = 0
            if isinstance(traffic, dict) and traffic:
                v = traffic.get("views") if isinstance(traffic.get("views"), dict) else {}
                c = traffic.get("clones") if isinstance(traffic.get("clones"), dict) else {}
                views_total = int(v.get("count") or 0)
                views_unique = int(v.get("uniques") or 0)
                clones_total = int(c.get("count") or 0)
                clones_unique = int(c.get("uniques") or 0)

            traffic_ok = "yes" if traffic and not traffic_err else ("no" if traffic_err else "n/a")
            if traffic_err:
                warnings.append(f"{repo_name}: traffic\n{traffic_err}")

            commits_err = str(r.get("commits_error") or "").strip()
            if commits_err:
                warnings.append(f"{repo_name}: commits\n{commits_err}")

            row_vals = [
                repo_name,
                str(commits),
                str(stars),
                str(forks),
                str(watchers),
                str(issues),
                str(rdl),
                str(views_total),
                str(views_unique),
                str(clones_total),
                str(clones_unique),
                traffic_ok,
            ]

            for col, val in enumerate(row_vals):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.UserRole, html_url)
                else:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, col, it)

        # 2. UNLOCK THE TABLE ONCE DATA IS LOADED
        self.table.setSortingEnabled(True)
        # details raw json
        self.details.setPlainText(json.dumps(data, indent=2))

        # errors tab = repo errors + warnings
        merged: List[str] = []
        if errs:
            merged.append("=== Errors (repo fetch) ===")
            merged.append(json.dumps(errs, indent=2))
        if warnings:
            merged.append("\n=== Warnings (traffic/commits) ===")
            merged.append("\n\n".join(warnings))
        self.errors.setPlainText("\n".join(merged).strip())

        # totals label
        if isinstance(totals, dict) and totals:
            self.totals_label.setText(
                f"Totals — repos: {totals.get('repos',0)} | "
                f"commits: {totals.get('commits_total',0)} | "
                f"stars: {totals.get('stars',0)} | forks: {totals.get('forks',0)} | "
                f"watchers: {totals.get('watchers',0)} | issues: {totals.get('open_issues',0)} | "
                f"release downloads: {totals.get('release_asset_downloads_total',0)} | "
                f"views(14d): {totals.get('views_14d_total',0)} ({totals.get('views_14d_unique',0)} unique) | "
                f"clones(14d): {totals.get('clones_14d_total',0)} ({totals.get('clones_14d_unique',0)} unique)"
            )
        else:
            self.totals_label.setText("")

        self.on_autofit()

    def on_autofit(self) -> None:
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)  # Repo
        for c in range(1, len(self.COLS)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)

    def on_open_repo(self, item: QTableWidgetItem) -> None:
        row = item.row()
        repo_cell = self.table.item(row, 0)
        if not repo_cell:
            return
        url = repo_cell.data(Qt.UserRole) or ""
        if url:
            QDesktopServices.openUrl(QUrl(str(url)))

    def on_export(self) -> None:
        if not self.last_data:
            QMessageBox.information(self, "Nothing to export", "Fetch analytics first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            str(app_dir() / "analytics.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.last_data, f, indent=2)
            QMessageBox.information(self, "Exported", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))


def run_gui() -> None:
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    w = MainWindow()
    w.resize(1320, 840)
    w.show()
    app.exec_()


# ✅ entrypoint
if __name__ == "__main__":
    run_gui()
