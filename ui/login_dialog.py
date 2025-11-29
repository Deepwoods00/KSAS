# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
    QMessageBox, QHBoxLayout, QCheckBox
)
from PySide6.QtCore import Qt
from i18n.i18n import get_text

class LoginDialog(QDialog):
    def __init__(self, keyauth_app, parent=None, initial_error=None):
        super().__init__(parent)
        self.keyauth_app = keyauth_app
        self.initial_error = initial_error
        self.setWindowTitle("KSAS Login")
        self.resize(350, 180)
        self.setup_ui()
        
        if self.initial_error:
            QMessageBox.warning(self, "Auto-Login Failed", f"Previous session invalid:\n{self.initial_error}")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        lbl_title = QLabel("KSAS")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #00695C;")
        layout.addWidget(lbl_title)

        # 输入框
        self.line_key = QLineEdit()
        self.line_key.setPlaceholderText("Enter License Key")
        self.line_key.setStyleSheet("padding: 8px; border: 1px solid #B2DFDB; border-radius: 4px;")
        layout.addWidget(self.line_key)

        # 记住卡密
        self.chk_remember = QCheckBox("Remember Key")
        self.chk_remember.setChecked(True)
        layout.addWidget(self.chk_remember)

        # 按钮
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Login")
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #009688; 
                color: white; 
                padding: 8px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00796B; }
        """)
        self.btn_login.clicked.connect(self.do_login)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def do_login(self):
        key = self.line_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Error", "Please enter a license key.")
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText("Verifying...")
        
        try:
            # 调用 KeyAuth 登录
            # license() returns None on success, or error message string on failure
            result = self.keyauth_app.license(key)
            
            if result is None: # Success
                if self.keyauth_app.check():
                    self.accept()
                else:
                    QMessageBox.critical(self, "Login Failed", "Session check failed after license verification.")
                    self.btn_login.setEnabled(True)
                    self.btn_login.setText("Login")
            else:
                # result contains the error message from KeyAuth
                QMessageBox.critical(self, "Login Failed", f"Verification failed:\n{result}")
                self.btn_login.setEnabled(True)
                self.btn_login.setText("Login")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection Error: {str(e)}")
            self.btn_login.setEnabled(True)
            self.btn_login.setText("Login")

    def get_key(self):
        return self.line_key.text().strip()