from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QPushButton, QMessageBox, QFormLayout
)
from airtest.core.android.adb import ADB
import os

class AddInstanceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加新实例")
        self.resize(400, 200)
        self.setup_ui()
        self.refresh_devices()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        
        # 实例名称
        self.line_name = QLineEdit()
        self.line_name.setPlaceholderText("例如: 主号, 小号1...")
        form.addRow("实例名称:", self.line_name)

        # 设备序列号
        hbox_serial = QHBoxLayout()
        self.combo_serial = QComboBox()
        self.combo_serial.setEditable(True)
        self.combo_serial.setPlaceholderText("选择或输入设备 Serial/IP:Port")
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setToolTip("刷新设备列表")
        btn_refresh.setFixedWidth(40)
        btn_refresh.clicked.connect(self.refresh_devices)
        
        hbox_serial.addWidget(self.combo_serial)
        hbox_serial.addWidget(btn_refresh)
        form.addRow("设备 Serial:", hbox_serial)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def refresh_devices(self):
        self.combo_serial.clear()
        try:
            # 1. 获取配置的 ADB 路径
            from config import global_config
            adb_path = global_config.get("adb_path", "")
            use_internal = global_config.get("use_internal_adb", True)
            
            # 如果使用内置，尝试构建路径 (这里假设在当前目录下有 adb/adb.exe)
            if use_internal:
                # 简单的内置路径推断，实际可能需要更严谨的判断
                if os.path.exists("adb/adb.exe"):
                    adb_path = os.path.abspath("adb/adb.exe")
                else:
                    # 如果没找到内置的，就让 Airtest 自己去找
                    adb_path = None
            
            # 2. 初始化 ADB
            if adb_path and os.path.exists(adb_path):
                adb = ADB(adb_path=adb_path)
            else:
                adb = ADB() # 尝试自动查找

            # 3. 获取设备列表
            devices = adb.devices() # returns list of (serial, status)
            
            count = 0
            for serial, status in devices:
                if status == 'device':
                    self.combo_serial.addItem(serial)
                    count += 1
            
            if count == 0:
                self.combo_serial.setPlaceholderText("未检测到在线设备")
            else:
                self.combo_serial.setPlaceholderText("请选择设备...")
                self.combo_serial.showPopup() # 自动弹出列表方便选择

        except Exception as e:
            print(f"Error refreshing devices: {e}")
            QMessageBox.warning(self, "ADB 错误", f"无法获取设备列表:\n{e}")

    def get_data(self):
        return self.line_name.text().strip(), self.combo_serial.currentText().strip()
