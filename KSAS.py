# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from PySide6.QtWidgets import QApplication, QStyleFactory

# 限制第三方库线程 (优化性能)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["PADDLE_NUM_THREADS"] = "1"
os.environ["OPENCV_NUM_THREADS"] = "1"

import logging
import airtest.core.api

# ==============================================================================
# 🩹 Monkeypatch: 修复打包后 Airtest 找不到 assets 图片的问题
# ==============================================================================
_original_template_init = airtest.core.api.Template.__init__

def _patched_template_init(self, filename, *args, **kwargs):
    if getattr(sys, 'frozen', False) and isinstance(filename, str):
        # 如果是相对路径，尝试在临时目录找
        if not os.path.isabs(filename):
            possible_path = os.path.join(sys._MEIPASS, filename)
            if os.path.exists(possible_path):
                filename = possible_path
    _original_template_init(self, filename, *args, **kwargs)

airtest.core.api.Template.__init__ = _patched_template_init
# ==============================================================================

from PySide6.QtWidgets import QApplication
from ui.main_window_logic import MainWindowLogic

from config import global_config
# 引入 Airtest 常量
from airtest.core.android import constant

# 引入 KeyAuth
from tools.keyauth.keyauth import api
from ui.login_dialog import LoginDialog
from tools.resource_loader import ResourceLoader
from i18n.i18n import get_text

def getchecksum():
    # 简单的 checksum 占位符，实际应读取文件 MD5
    return "checksum_placeholder"

def init_keyauth():
    return api(
        name = "KSAS",
        ownerid = "NVEZ7gY47U",
        version = "1.0",
        hash_to_check = getchecksum()
    )

def setup_global_adb():
    """
    设置 Airtest 全局 ADB 路径 (绝对路径 + 和平共处版)
    """
    logger.info("-" * 30)
    logger.info(get_text("log_adb_init"))
    
    use_internal = global_config.get("use_internal_adb", True)
    custom_path = global_config.get("adb_path", "")
    
    target_adb = None
    
    # 1. 【核心修改】获取 KSAS.py 文件所在的绝对目录
    # 这确保了无论脚本在哪里运行，都能找到旁边的 tools 文件夹
    if getattr(sys, 'frozen', False):
        project_root = sys._MEIPASS
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
    
    if use_internal:
        # 拼接绝对路径
        internal_path = os.path.join(project_root, "tools", "adb", "adb.exe")
        if os.path.exists(internal_path):
            target_adb = internal_path
        else:
            logger.error(get_text("log_adb_internal_not_found", internal_path))
    elif custom_path and os.path.exists(custom_path):
        target_adb = custom_path
            
    if target_adb:
        adb_dir = os.path.dirname(target_adb)
        logger.info(get_text("log_adb_target_locked", target_adb))
        
        # 2. 【核心】修改 Airtest 内部常量
        constant.ADB_PATH = target_adb
        
        # 3. 【核心】将我们的 ADB 目录插入系统 PATH 的第一位
        # 这能拦截大部分直接调用 "adb" 命令的库
        os.environ["PATH"] = adb_dir + os.pathsep + os.environ["PATH"]

        # 4. 【核心】修正 adbutils 库的指向 (如果有的话)
        # 这就是解决你刚才看到“指向 site-packages”问题的关键
        try:
            import adbutils
            adbutils._adb_path = target_adb
            logger.info("[System] adbutils path corrected")
        except ImportError:
            pass
            
    else:
        logger.warning(get_text("log_adb_fallback"))
    
    logger.info("-" * 30)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Main")

if __name__ == "__main__":
    # 1. 配置 ADB (最优先执行)
    setup_global_adb()

    # 2. 启动 UI
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    # --- KeyAuth 验证流程 ---
    keyauthapp = init_keyauth()
    
    saved_key = global_config.get("license_key", "")
    is_logged_in = False
    auto_login_error = None

    # A. 尝试自动登录
    if saved_key:
        logger.info(get_text("log_keyauth_auto_login"))
        try:
            # logger.debug(f"Verifying key: {saved_key}")
            auth_result = keyauthapp.license(saved_key)
            
            if auth_result is None: # Success
                # logger.debug("License check passed.")
                if keyauthapp.check():
                    logger.info(get_text("log_keyauth_success"))
                    is_logged_in = True
            else:
                # auth_result is the error message
                logger.error(get_text("log_keyauth_fail", auth_result))
                auto_login_error = auth_result
                
        except Exception as e:
            logger.error(get_text("log_keyauth_fail", e))
            auto_login_error = str(e)

    
    # B. 弹出登录框
    if not is_logged_in:
        dialog = LoginDialog(keyauthapp, initial_error=auto_login_error)
        if dialog.exec():
            is_logged_in = True
            # 保存卡密
            if dialog.chk_remember.isChecked():
                global_config.set("license_key", dialog.get_key())
        else:
            sys.exit(0)


    if is_logged_in:
        logger.info("[System] Initializing Secure Resource Loader...")
        ResourceLoader().initialize(keyauthapp)
        # (可选) 这里可以预先测试下载，如果核心资源挂了直接不启动
        # test_img = ResourceLoader().get_template("你的_HOME_CHECK_FILE_ID")
        # if not test_img: sys.exit("Critical Asset Missing")
    
    # 强制使用 Tiffany Blue 风格浅色主题
    # Tiffany Blue: #0ABAB5 (标准), #81D8D0 (经典), #E0F2F1 (极浅背景)
    app.setStyleSheet("""
        /* ================= 全局基础设置 ================= */
        QWidget {
            background-color: #E0F2F1; /* 极浅的青色背景 */
            color: #004D40;            /* 深青色文字 (强制) */
            font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        }
        
        /* 强制弹窗和消息框也使用这个背景，防止变成黑色 */
        QDialog, QMessageBox {
            background-color: #E0F2F1;
        }

        /* 鼠标悬停提示 */
        QToolTip {
            background-color: #ffffff;
            color: #004D40;
            border: 1px solid #009688;
            padding: 5px;
            border-radius: 4px;
            font-family: "Microsoft YaHei";
            font-size: 10pt;
        }

        /* ================= 分组框 (GroupBox) ================= */
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #80CBC4;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #00695C;
            font-weight: bold;
            background-color: #E0F2F1; /* 标题背景与主背景一致 */
            border-radius: 3px;
        }
        QGroupBox::indicator {
            width: 18px;
            height: 18px;
            margin-left: 5px;
        }
        QGroupBox::indicator:unchecked {
            background-color: #ffffff;
            border: 1px solid #B2DFDB;
            border-radius: 3px;
        }
        QGroupBox::indicator:checked {
            background-color: #009688;
            border: 1px solid #009688;
            border-radius: 3px;
        }

        /* ================= 复选框 (CheckBox) ================= */
        QCheckBox {
            spacing: 5px;
            color: #004D40; /* 强制文字颜色 */
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #009688;
            border-radius: 3px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:unchecked {
            background-color: #ffffff;
        }
        QCheckBox::indicator:checked {
            background-color: #009688;
            border: 1px solid #009688;
        }
        QCheckBox::indicator:unchecked:hover {
            border: 1px solid #00796B;
        }

        /* ================= 输入控件 (核心修复区) ================= */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #ffffff;      /* 强制白底 */
            color: #004D40;                 /* 强制深青色字 */
            border: 1px solid #B2DFDB;
            border-radius: 4px;
            padding: 4px;
            selection-background-color: #80CBC4; /* 选中时的背景色 */
            selection-color: #ffffff;            /* 选中时的文字色 */
        }
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
            border: 1px solid #009688;
        }
        
        /* 👇【关键修复】占位符文字颜色 (例如 "请输入卡密") */
        /* 如果不加这行，深色模式下 Qt 会把它设成白色，导致看不见 */
        QLineEdit::placeholder {
            color: #9E9E9E; 
        }

        /* 👇【关键修复】修复下拉框弹出层的颜色 */
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #004D40;
            selection-background-color: #B2DFDB;
            selection-color: #004D40;
            outline: none;
        }

        /* ================= 列表与文本域 ================= */
        QListWidget, QTextEdit {
            background-color: #ffffff;
            border: 1px solid #B2DFDB;
            border-radius: 4px;
            color: #004D40;
        }
        QListWidget::item:selected {
            background-color: #B2DFDB;
            color: #004D40;
        }

        /* ================= 按钮 ================= */
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #009688;
            color: #009688;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #E0F2F1;
        }
        QPushButton:pressed {
            background-color: #B2DFDB;
        }
        
        /* 特殊按钮状态 */
        QPushButton[state="running"] {
            background-color: #FFEBEE;
            border-color: #EF5350;
            color: #C62828;
        }
        QPushButton[state="stopped"] {
            background-color: #E8F5E9;
            border-color: #66BB6A;
            color: #2E7D32;
        }

        /* ================= 滚动区域与滚动条 ================= */
        QScrollArea {
            background-color: transparent;
            border: none;
        }
        
        QScrollBar:vertical {
            border: none;
            background: #E0F2F1;
            width: 8px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #80CBC4;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        /* ================= 折叠框按钮 ================= */
        QToolButton {
            background-color: #B2DFDB;
            color: #00695C;
            border: none;
            border-radius: 4px;
            padding: 5px;
            font-weight: bold;
        }
        QToolButton:hover {
            background-color: #80CBC4;
        }
        QToolButton:checked {
            background-color: #4DB6AC;
            color: #ffffff;
        }
    """)

    window = MainWindowLogic(keyauth_app=keyauthapp)
    window.show()
    
    logger.info(get_text("log_ui_launched"))
    sys.exit(app.exec())