from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QHBoxLayout, QCheckBox, QComboBox, QFrame,
    QApplication
)
from PySide6.QtCore import Qt
from i18n.i18n import get_text
from config import global_config # 引入配置以保存语言设置

class LoginDialog(QDialog):
    def __init__(self, keyauth_app, parent=None, initial_error=None):
        super().__init__(parent)
        self.keyauth_app = keyauth_app
        self.initial_error = initial_error
        
        # 初始化界面
        self.setup_ui()
        
        # 如果有自动登录错误，弹窗提示
        if self.initial_error:
            # 注意：这里的文本需要手动获取一次，因为 retranslate_ui 还没执行
            QMessageBox.warning(self, get_text("msg_auto_login_failed"), get_text("msg_prev_session_invalid", self.initial_error))

    def setup_ui(self):
        self.resize(380, 220) # 稍微调高一点高度
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 顶部：标题 + 语言切换 (用水平布局)
        top_layout = QHBoxLayout()
        
        self.lbl_title = QLabel("KSAS")
        self.lbl_title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #00695C;")

        self.lbl_lang_hint = QLabel("语言/Language:")
        self.lbl_lang_hint.setStyleSheet("color: #666666; font-size: 9pt; margin-right: 2px;")
        
        # 语言下拉框
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["简体中文", "English"])
        self.combo_lang.setFocusPolicy(Qt.NoFocus)
        self.combo_lang.setFixedWidth(90)
        
        # 读取当前配置并设置选中项
        current_lang = global_config.get("language", "zh_CN")
        if "en" in current_lang:
            self.combo_lang.setCurrentIndex(1)
        else:
            self.combo_lang.setCurrentIndex(0)
            
        # 连接信号
        self.combo_lang.currentIndexChanged.connect(self.on_language_changed)

        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch() # 弹簧
        top_layout.addWidget(self.lbl_lang_hint)
        top_layout.addWidget(self.combo_lang) # 语言放右上角
        
        self.main_layout.addLayout(top_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(line)

        # 2. 输入框
        self.line_key = QLineEdit()
        self.line_key.setStyleSheet("padding: 8px; border: 1px solid #B2DFDB; border-radius: 4px;")
        self.main_layout.addWidget(self.line_key)

        # 3. 记住卡密
        self.chk_remember = QCheckBox()
        self.chk_remember.setChecked(True)
        self.main_layout.addWidget(self.chk_remember)

        # 4. 按钮区域
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton()
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
        
        self.btn_cancel = QPushButton()
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #555555;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                color: #333333;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_cancel)
        self.main_layout.addLayout(btn_layout)
        
        # 初始化文本
        self.retranslate_ui()

    def on_language_changed(self, index):
        """当语言切换时触发"""
        lang_code = "zh_CN" if index == 0 else "en_US"
        
        # 1. 保存配置
        global_config.set("language", lang_code)
        
        # 2. 立即刷新当前界面的文字
        self.retranslate_ui()

    def retranslate_ui(self):
        """刷新界面上的所有文本"""
        self.setWindowTitle(get_text("title_login"))
        self.line_key.setPlaceholderText(get_text("lbl_enter_key"))
        self.chk_remember.setText(get_text("chk_remember_key"))
        self.btn_login.setText(get_text("btn_login"))
        self.btn_cancel.setText(get_text("btn_cancel_simple"))

    def do_login(self):
        key = self.line_key.text().strip()
        if not key:
            QMessageBox.warning(self, get_text("msg_error"), get_text("msg_enter_key"))
            return

        self.btn_login.setEnabled(False)
        self.btn_login.setText(get_text("btn_verifying"))
        
        # 这里为了防止界面卡死，简单的逻辑可以直接跑，
        # 如果 keyauth 验证很慢，建议用 QThread，但登录框一般允许短时阻塞
        QApplication.processEvents() # 刷新一下UI显示 "Verifying..."

        try:
            # 调用 KeyAuth 登录
            result = self.keyauth_app.license(key)
            
            if result is None: # Success
                if self.keyauth_app.check():
                    self.accept()
                else:
                    self.show_error(get_text("msg_session_check_fail"))
            else:
                self.show_error(get_text("msg_verify_fail", result))
                
        except Exception as e:
            self.show_error(get_text("msg_conn_error", str(e)))

    def show_error(self, msg):
        QMessageBox.critical(self, get_text("msg_login_failed"), msg)
        self.btn_login.setEnabled(True)
        self.btn_login.setText(get_text("btn_login"))

    def get_key(self):
        return self.line_key.text().strip()
