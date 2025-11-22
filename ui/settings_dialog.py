# -*- coding: utf-8 -*-
import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QCheckBox, QComboBox, QLineEdit, QPushButton, 
    QFileDialog, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from config import global_config
from i18n.i18n import get_text

class SettingsDialog(QDialog):
    sig_config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("btn_global_settings"))
        self.resize(500, 400)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: 通用设置
        self.tab_general = QWidget()
        self.setup_general_tab()
        self.tabs.addTab(self.tab_general, get_text("tab_general"))

        # Tab 2: ADB 设置
        self.tab_adb = QWidget()
        self.setup_adb_tab()
        self.tabs.addTab(self.tab_adb, get_text("tab_adb"))

        # Tab 3: 数据管理
        self.tab_data = QWidget()
        self.setup_data_tab()
        self.tabs.addTab(self.tab_data, get_text("tab_data"))

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_save = QPushButton(get_text("btn_save"))
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton(get_text("btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def setup_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        
        # 语言
        group_lang = QGroupBox(get_text("grp_language"))
        form_lang = QFormLayout()
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["简体中文 (zh_CN)", "English (en_US)"])
        form_lang.addRow(get_text("grp_language") + ":", self.combo_lang)
        group_lang.setLayout(form_lang)
        layout.addWidget(group_lang)

        # 行为
        group_behavior = QGroupBox(get_text("grp_behavior"))
        vbox = QVBoxLayout()
        self.chk_close_tray = QCheckBox(get_text("chk_close_tray"))
        self.chk_auto_connect = QCheckBox(get_text("chk_auto_connect"))
        vbox.addWidget(self.chk_close_tray)
        vbox.addWidget(self.chk_auto_connect)
        group_behavior.setLayout(vbox)
        layout.addWidget(group_behavior)

        layout.addStretch()

    def setup_adb_tab(self):
        layout = QVBoxLayout(self.tab_adb)

        group_path = QGroupBox(get_text("grp_adb_path"))
        vbox = QVBoxLayout()
        
        self.chk_internal_adb = QCheckBox(get_text("chk_internal_adb"))
        self.chk_internal_adb.toggled.connect(self.on_internal_adb_toggled)
        vbox.addWidget(self.chk_internal_adb)

        hbox = QHBoxLayout()
        self.line_adb_path = QLineEdit()
        self.line_adb_path.setPlaceholderText("Select adb.exe path...")
        btn_browse = QPushButton(get_text("btn_browse"))
        btn_browse.clicked.connect(self.browse_adb)
        hbox.addWidget(self.line_adb_path)
        hbox.addWidget(btn_browse)
        vbox.addLayout(hbox)
        
        group_path.setLayout(vbox)
        layout.addWidget(group_path)

        # 工具
        group_tools = QGroupBox(get_text("grp_adb_tools"))
        hbox_tools = QHBoxLayout()
        btn_restart_adb = QPushButton(get_text("btn_restart_adb"))
        btn_restart_adb.clicked.connect(self.restart_adb_server)
        hbox_tools.addWidget(btn_restart_adb)
        group_tools.setLayout(hbox_tools)
        layout.addWidget(group_tools)

        layout.addStretch()

    def setup_data_tab(self):
        layout = QVBoxLayout(self.tab_data)

        group_backup = QGroupBox(get_text("grp_backup"))
        vbox = QVBoxLayout()
        
        btn_backup = QPushButton(get_text("btn_backup"))
        btn_backup.clicked.connect(self.backup_data)
        
        btn_restore = QPushButton(get_text("btn_restore"))
        btn_restore.clicked.connect(self.restore_data)

        vbox.addWidget(btn_backup)
        vbox.addWidget(btn_restore)
        group_backup.setLayout(vbox)
        layout.addWidget(group_backup)

        group_explore = QGroupBox(get_text("grp_explorer"))
        hbox = QHBoxLayout()
        btn_open_data = QPushButton(get_text("btn_open_data"))
        btn_open_data.clicked.connect(lambda: self.open_folder("data"))
        hbox.addWidget(btn_open_data)
        group_explore.setLayout(hbox)
        layout.addWidget(group_explore)

        layout.addStretch()

    # ================= Logic =================

    def load_settings(self):
        # Language
        lang = global_config.get("language", "zh_CN")
        idx = 0 if lang == "zh_CN" else 1
        self.combo_lang.setCurrentIndex(idx)

        # Behavior
        self.chk_close_tray.setChecked(global_config.get("close_to_tray", True))
        self.chk_auto_connect.setChecked(global_config.get("auto_connect", True))

        # ADB
        use_internal = global_config.get("use_internal_adb", True)
        self.chk_internal_adb.setChecked(use_internal)
        self.line_adb_path.setText(global_config.get("adb_path", ""))
        self.line_adb_path.setEnabled(not use_internal)

    def save_settings(self):
        # Language
        lang = "zh_CN" if self.combo_lang.currentIndex() == 0 else "en_US"
        global_config.set("language", lang)

        # Behavior
        global_config.set("close_to_tray", self.chk_close_tray.isChecked())
        global_config.set("auto_connect", self.chk_auto_connect.isChecked())

        # ADB
        global_config.set("use_internal_adb", self.chk_internal_adb.isChecked())
        global_config.set("adb_path", self.line_adb_path.text().strip())

        global_config.save()
        self.sig_config_changed.emit()
        self.accept()

    def on_internal_adb_toggled(self, checked):
        self.line_adb_path.setEnabled(not checked)

    def browse_adb(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 ADB", "", "Executable (*.exe);;All Files (*)")
        if path:
            self.line_adb_path.setText(path)

    def restart_adb_server(self):
        try:
            subprocess.run(["adb", "kill-server"], check=False)
            subprocess.run(["adb", "start-server"], check=False)
            QMessageBox.information(self, get_text("msg_success"), get_text("msg_adb_restarted"))
        except Exception as e:
            QMessageBox.warning(self, get_text("msg_error"), f"Failed: {e}")

    def backup_data(self):
        try:
            # 确保 backup 文件夹存在
            backup_dir = "backup"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(backup_dir, f"backup_{timestamp}.zip")
            
            with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists("data"):
                    for root, dirs, files in os.walk("data"):
                        for file in files:
                            # 排除截图文件夹，太大了
                            if "snapshots" in root:
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, ".")
                            zipf.write(file_path, arcname)
            
            QMessageBox.information(self, get_text("msg_success"), get_text("msg_backup_success").format(os.path.abspath(filename)))
        except Exception as e:
            QMessageBox.critical(self, get_text("msg_error"), str(e))

    def restore_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Backup", "", "Zip Files (*.zip)")
        if not path:
            return

        reply = QMessageBox.question(
            self, "Confirm Restore",
            get_text("msg_restore_confirm"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with zipfile.ZipFile(path, 'r') as zipf:
                    zipf.extractall(".")
                QMessageBox.information(self, get_text("msg_success"), get_text("msg_restore_success"))
            except Exception as e:
                QMessageBox.critical(self, get_text("msg_error"), str(e))

    def open_folder(self, folder):
        path = os.path.abspath(folder)
        if not os.path.exists(path):
            os.makedirs(path)
        os.startfile(path)
