# ui/edit_instance_dialog.py
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QSpinBox, QLabel, QAbstractSpinBox
)
from i18n.i18n import get_text

class EditInstanceDialog(QDialog):
    def __init__(self, parent=None, current_name="", current_serial="", current_diana=0, current_march_slots=5):
        super().__init__(parent)
        self.setWindowTitle(get_text("title_edit_instance"))
        self.resize(350, 250)
        
        # 记录原始数据
        self.old_name = current_name
        self.old_serial = current_serial
        self.old_diana = current_diana
        self.old_march_slots = current_march_slots
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 表单区域
        form = QFormLayout()
        
        # 1. 名字
        self.line_name = QLineEdit(self.old_name)
        self.line_name.setPlaceholderText(get_text("ph_instance_name"))
        form.addRow(get_text("lbl_name"), self.line_name)
        
        # 2. 地址
        self.line_serial = QLineEdit(self.old_serial)
        self.line_serial.setPlaceholderText(get_text("ph_serial"))
        form.addRow(get_text("lbl_address"), self.line_serial)
        
        # 3. Diana 等级 (新增)
        self.spin_diana = QSpinBox()
        self.spin_diana.setRange(0, 5) # 0表示没有，1-5是等级
        self.spin_diana.setValue(int(self.old_diana))
        self.spin_diana.setSuffix(" Lv")
        self.spin_diana.setButtonSymbols(QAbstractSpinBox.NoButtons)
        # 加个小提示
        lbl_tip = QLabel(get_text("tip_diana"))
        lbl_tip.setStyleSheet("color: gray; font-size: 9pt;")
        
        form.addRow(get_text("lbl_diana"), self.spin_diana)
        form.addRow("", lbl_tip) # 占位显示提示

        # 4. 行军队列 (新增)
        self.spin_march = QSpinBox()
        self.spin_march.setRange(1, 6)
        self.spin_march.setValue(int(self.old_march_slots))
        self.spin_march.setButtonSymbols(QAbstractSpinBox.NoButtons)
        
        lbl_tip_march = QLabel(get_text("tip_march_slots"))
        lbl_tip_march.setStyleSheet("color: gray; font-size: 9pt;")
        
        form.addRow(get_text("lbl_march_slots"), self.spin_march)
        form.addRow("", lbl_tip_march)
        
        layout.addLayout(form)

        # 按钮区域 (确定/取消)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """返回: (name, serial, diana_level, march_slots)"""
        return (
            self.line_name.text().strip(),
            self.line_serial.text().strip(),
            self.spin_diana.value(),
            self.spin_march.value()
        )