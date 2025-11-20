# ui/edit_instance_dialog.py
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QMessageBox
)

class EditInstanceDialog(QDialog):
    def __init__(self, parent=None, current_name="", current_serial=""):
        super().__init__(parent)
        self.setWindowTitle("修改实例信息")
        self.resize(350, 150)
        
        # 记录原始数据
        self.old_name = current_name
        self.old_serial = current_serial
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 表单区域
        form = QFormLayout()
        
        self.line_name = QLineEdit(self.old_name)
        self.line_name.setPlaceholderText("给它起个新名字")
        
        self.line_serial = QLineEdit(self.old_serial)
        self.line_serial.setPlaceholderText("例如: 127.0.0.1:5555")
        
        form.addRow("实例名称:", self.line_name)
        form.addRow("设备地址:", self.line_serial)
        
        layout.addLayout(form)

        # 按钮区域 (确定/取消)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """返回修改后的数据"""
        return self.line_name.text().strip(), self.line_serial.text().strip()