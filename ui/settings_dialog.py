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

class SettingsDialog(QDialog):
    sig_config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全局设置")
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
        self.tabs.addTab(self.tab_general, "通用")

        # Tab 2: ADB 设置
        self.tab_adb = QWidget()
        self.setup_adb_tab()
        self.tabs.addTab(self.tab_adb, "ADB")

        # Tab 3: 数据管理
        self.tab_data = QWidget()
        self.setup_data_tab()
        self.tabs.addTab(self.tab_data, "数据管理")

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def setup_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        
        # 语言
        group_lang = QGroupBox("语言 / Language")
        form_lang = QFormLayout()
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["简体中文 (zh_CN)", "English (en_US)"])
        form_lang.addRow("界面语言:", self.combo_lang)
        group_lang.setLayout(form_lang)
        layout.addWidget(group_lang)

        # 行为
        group_behavior = QGroupBox("行为设置")
        vbox = QVBoxLayout()
        self.chk_close_tray = QCheckBox("关闭窗口时最小化到托盘")
        self.chk_auto_connect = QCheckBox("启动时自动连接上次设备")
        vbox.addWidget(self.chk_close_tray)
        vbox.addWidget(self.chk_auto_connect)
        group_behavior.setLayout(vbox)
        layout.addWidget(group_behavior)

        layout.addStretch()

    def setup_adb_tab(self):
        layout = QVBoxLayout(self.tab_adb)

        group_path = QGroupBox("ADB 路径")
        vbox = QVBoxLayout()
        
        self.chk_internal_adb = QCheckBox("使用内置 ADB (推荐)")
        self.chk_internal_adb.toggled.connect(self.on_internal_adb_toggled)
        vbox.addWidget(self.chk_internal_adb)

        hbox = QHBoxLayout()
        self.line_adb_path = QLineEdit()
        self.line_adb_path.setPlaceholderText("选择 adb.exe 路径...")
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self.browse_adb)
        hbox.addWidget(self.line_adb_path)
        hbox.addWidget(btn_browse)
        vbox.addLayout(hbox)
        
        group_path.setLayout(vbox)
        layout.addWidget(group_path)

        # 工具
        group_tools = QGroupBox("ADB 工具")
        hbox_tools = QHBoxLayout()
        btn_restart_adb = QPushButton("重启 ADB 服务")
        btn_restart_adb.clicked.connect(self.restart_adb_server)
        hbox_tools.addWidget(btn_restart_adb)
        group_tools.setLayout(hbox_tools)
        layout.addWidget(group_tools)

        layout.addStretch()

    def setup_data_tab(self):
        layout = QVBoxLayout(self.tab_data)

        group_backup = QGroupBox("备份与还原")
        vbox = QVBoxLayout()
        
        btn_backup = QPushButton("📦 一键备份所有数据 (Backup)")
        btn_backup.clicked.connect(self.backup_data)
        
        btn_restore = QPushButton("♻️ 从备份还原数据 (Restore)")
        btn_restore.clicked.connect(self.restore_data)

        vbox.addWidget(btn_backup)
        vbox.addWidget(btn_restore)
        group_backup.setLayout(vbox)
        layout.addWidget(group_backup)

        group_explore = QGroupBox("文件浏览")
        hbox = QHBoxLayout()
        btn_open_data = QPushButton("📂 打开 Data 文件夹")
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
            QMessageBox.information(self, "成功", "ADB 服务已重启")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"重启 ADB 失败: {e}")

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
            
            QMessageBox.information(self, "备份成功", f"已创建备份文件:\n{os.path.abspath(filename)}")
        except Exception as e:
            QMessageBox.critical(self, "备份失败", str(e))

    def restore_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择备份文件", "", "Zip Files (*.zip)")
        if not path:
            return

        reply = QMessageBox.question(
            self, "确认还原", 
            "还原操作将覆盖当前的配置文件，确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                with zipfile.ZipFile(path, 'r') as zipf:
                    zipf.extractall(".")
                QMessageBox.information(self, "还原成功", "数据已还原，请重启程序以生效。")
            except Exception as e:
                QMessageBox.critical(self, "还原失败", str(e))

    def open_folder(self, folder):
        path = os.path.abspath(folder)
        if not os.path.exists(path):
            os.makedirs(path)
        os.startfile(path)
