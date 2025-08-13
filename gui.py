import sys
import os
import pathlib
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QProgressBar,
    QMessageBox,
)

import prints
from config_loader import load_config
from core import core as Core
import findjava


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class LauncherGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WNLauncher GUI")
        self.resize(980, 680)

        self.cfg = load_config()
        self.core = Core()
        self.current_type = "release"  # release | snapshot | old
        self.all_versions: Dict[str, List[Dict[str, Any]]] = {}
        self.java_list: List[List[str]] = []  # [path, version, arch]

        self._build_ui()
        self._apply_style()
        self._load_javas()
        self._fetch_versions(self.current_type)

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Top controls
        top = QHBoxLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["release", "snapshot", "old"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索版本，例如 1.20.1 …")
        self.search_edit.textChanged.connect(self._filter_list)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(lambda: self._fetch_versions(self.current_type))

        self.java_combo = QComboBox()
        self.java_combo.setMinimumWidth(280)

        top.addWidget(QLabel("类型"))
        top.addWidget(self.type_combo)
        top.addSpacing(10)
        top.addWidget(QLabel("搜索"))
        top.addWidget(self.search_edit, 1)
        top.addSpacing(10)
        top.addWidget(QLabel("Java"))
        top.addWidget(self.java_combo)
        top.addSpacing(10)
        top.addWidget(self.refresh_btn)
        root.addLayout(top)

        # List
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._prefill_name)
        root.addWidget(self.list_widget, 1)

        # Bottom actions
        bottom = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("安装名称（默认使用版本号）")

        self.download_btn = QPushButton("下载/安装")
        self.download_btn.clicked.connect(self.on_download)

        self.launch_btn = QPushButton("启动")
        self.launch_btn.clicked.connect(self.on_launch)

        bottom.addWidget(QLabel("安装名称"))
        bottom.addWidget(self.name_edit, 1)
        bottom.addSpacing(12)
        bottom.addWidget(self.download_btn)
        bottom.addWidget(self.launch_btn)
        root.addLayout(bottom)

        # Status
        status = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setVisible(False)
        status.addWidget(self.status_label, 1)
        status.addWidget(self.progress)
        root.addLayout(status)

        self.setCentralWidget(central)

    def _apply_style(self):
        # Simple modern dark style
        self.setStyleSheet(
            """
            QWidget { background-color: #111318; color: #F0F1F5; font-size: 14px; }
            QLineEdit, QComboBox { background: #181C23; border: 1px solid #2A2F3A; border-radius: 6px; padding: 6px 8px; }
            QPushButton { background: #2B5CFF; border: none; padding: 8px 14px; border-radius: 8px; color: white; }
            QPushButton:hover { background: #2F66FF; }
            QPushButton:disabled { background: #3A3F4D; color: #9AA1AF; }
            QListWidget { background: #151922; border: 1px solid #2A2F3A; border-radius: 8px; }
            QLabel { color: #D9DCE3; }
            QProgressBar { background: #151922; border: 1px solid #2A2F3A; border-radius: 6px; height: 10px; }
            QProgressBar::chunk { background: #2B5CFF; border-radius: 5px; }
            """
        )

    def _load_javas(self):
        try:
            self.java_list = findjava.main()
        except Exception:
            self.java_list = []
        self.java_combo.clear()
        if not self.java_list:
            self.java_combo.addItem("未找到Java (将尝试系统默认)")
        else:
            for p, ver, arch in self.java_list:
                self.java_combo.addItem(f"{ver} {arch} — {p}")

    def _fetch_versions(self, vtype: str):
        self._set_busy(True, "获取版本列表中…")

        def work():
            data = self.core.show_all_version()
            if data.get("status") != "success":
                raise RuntimeError("无法获取版本清单")
            return data

        self._run_async(work, self._on_versions_loaded, self._on_async_failed)

    def _on_versions_loaded(self, data):
        # Cache
        self.all_versions = {
            "release": data.get("all_release_version", []),
            "snapshot": data.get("all_snapshot_version", []),
            "old": data.get("all_old_version", []),
        }
        self._populate_list(self.current_type)
        self._set_busy(False, "已加载版本")

    def _populate_list(self, vtype: str):
        self.list_widget.clear()
        for v in self.all_versions.get(vtype, []):
            vid = v.get("id")
            vtime = v.get("releaseTime", v.get("time", ""))
            item = QListWidgetItem(f"{vid}    {v.get('type')}    {vtime}")
            item.setData(Qt.UserRole, v)
            self.list_widget.addItem(item)

    def _filter_list(self, text: str):
        text = text.strip().lower()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setHidden(text not in it.text().lower())

    def _prefill_name(self, item: QListWidgetItem):
        v = item.data(Qt.UserRole)
        if v:
            self.name_edit.setText(v.get("id", ""))

    def on_type_changed(self, t: str):
        self.current_type = t
        if not self.all_versions:
            self._fetch_versions(t)
        else:
            self._populate_list(t)

    def on_download(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先在列表中选择一个版本")
            return
        v = item.data(Qt.UserRole)
        vid = v.get("id")
        name = self.name_edit.text().strip() or vid

        self._set_busy(True, f"正在下载 {vid}…")
        def work():
            return self.core.download(self.current_type, vid, name)
        self._run_async(work, self._on_download_done, self._on_async_failed)

    def _on_download_done(self, result):
        status, msg = result
        self._set_busy(False, msg)
        if status == "success":
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "失败", msg)

    def on_launch(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, "提示", "请先选择一个版本")
            return
        v = item.data(Qt.UserRole)
        vid = v.get("id")
        name = self.name_edit.text().strip() or vid

        java_path: Optional[str] = None
        if self.java_list:
            idx = self.java_combo.currentIndex()
            if 0 <= idx < len(self.java_list):
                java_path = self.java_list[idx][0]

        self._set_busy(True, f"正在启动 {name}…")
        game_dir = pathlib.Path(self.cfg["launcher"]["game_path"][self.cfg["launcher"]["latest_game_path_used"]]) / "versions" / name
        if not game_dir.exists():
            self._set_busy(False, "")
            QMessageBox.warning(self, "提示", f"未找到安装目录：{game_dir}\n请先下载/安装该版本。")
            return

        def work():
            # Use the non-interactive launcher method if available
            if hasattr(self.core, "launch_version"):
                return self.core.launch_version(name, java_path=java_path)
            # Fallback: still attempt runMC but it is interactive; we avoid it here
            raise RuntimeError("当前版本不支持GUI启动（缺少 launch_version 方法）")

        self._run_async(work, self._on_launch_done, self._on_async_failed)

    def _on_launch_done(self, result):
        if isinstance(result, list) and result and result[0] == "success":
            self._set_busy(False, "游戏已启动")
        else:
            self._set_busy(False, "启动流程结束")

    def _set_busy(self, busy: bool, text: str = ""):
        self.status_label.setText(text)
        self.progress.setVisible(busy)
        self.refresh_btn.setEnabled(not busy)
        self.download_btn.setEnabled(not busy)
        self.launch_btn.setEnabled(not busy)
        self.type_combo.setEnabled(not busy)

    def _run_async(self, fn, on_ok, on_fail):
        self.worker = Worker(fn)
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(lambda r: self._cleanup_thread(on_ok, r))
        self.worker.failed.connect(lambda e: self._cleanup_thread(on_fail, e))
        self.thread.start()

    def _cleanup_thread(self, callback, payload):
        try:
            callback(payload)
        finally:
            try:
                self.thread.quit()
                self.thread.wait(2000)
            except Exception:
                pass


def main():
    app = QApplication(sys.argv)
    w = LauncherGUI()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())