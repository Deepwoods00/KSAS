# -*- coding: utf-8 -*-
import sys
import os
import subprocess

# 限制第三方库线程 (优化性能)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["PADDLE_NUM_THREADS"] = "1"
os.environ["OPENCV_NUM_THREADS"] = "1"

import logging
from PySide6.QtWidgets import QApplication
from ui.main_window_logic import MainWindowLogic

from config import global_config
# 引入 Airtest 常量
from airtest.core.android import constant

# 引入 KeyAuth
from tools.keyauth.keyauth import api
from ui.login_dialog import LoginDialog
from tools.resource_loader import ResourceLoader

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
    print("-" * 30)
    print("[System] 正在初始化 ADB 设置...")
    
    use_internal = global_config.get("use_internal_adb", True)
    custom_path = global_config.get("adb_path", "")
    
    target_adb = None
    
    # 1. 【核心修改】获取 KSAS.py 文件所在的绝对目录
    # 这确保了无论脚本在哪里运行，都能找到旁边的 tools 文件夹
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    if use_internal:
        # 拼接绝对路径
        internal_path = os.path.join(project_root, "tools", "adb", "adb.exe")
        if os.path.exists(internal_path):
            target_adb = internal_path
        else:
            print(f"❌ [System] 内置 ADB 文件未找到: {internal_path}")
            print("   (请确保 tools/adb/adb.exe 存在且结构正确)")
    elif custom_path and os.path.exists(custom_path):
        target_adb = custom_path
            
    if target_adb:
        adb_dir = os.path.dirname(target_adb)
        print(f"✅ [System] 锁定目标 ADB: {target_adb}")
        
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
            print("[System] 已修正 adbutils 库的路径指向")
        except ImportError:
            pass 
            
    else:
        print("⚠️ [System] 未找到指定 ADB，将使用系统默认路径 (可能会导致兼容性问题)")
    
    print("-" * 30)

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

    # --- KeyAuth 验证流程 ---
    keyauthapp = init_keyauth()
    
    saved_key = global_config.get("license_key", "")
    is_logged_in = False
    auto_login_error = None

    # A. 尝试自动登录
    if saved_key:
        print(f"[KeyAuth] 尝试自动登录...")
        try:
            print(f"[Debug] Verifying key: {saved_key}")
            auth_result = keyauthapp.license(saved_key)
            
            if auth_result is None: # Success
                print(f"[Debug] License check passed.")
                if keyauthapp.check():
                    print(f"[KeyAuth] 自动登录成功")
                    is_logged_in = True
            else:
                # auth_result is the error message
                print(f"[KeyAuth] 自动登录失败: {auth_result}")
                auto_login_error = auth_result
                
        except Exception as e:
            print(f"[KeyAuth] 自动登录失败: {e}")
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
        print("[System] Initializing Secure Resource Loader...")
        ResourceLoader().initialize(keyauthapp)
        # (可选) 这里可以预先测试下载，如果核心资源挂了直接不启动
        # test_img = ResourceLoader().get_template("你的_HOME_CHECK_FILE_ID")
        # if not test_img: sys.exit("Critical Asset Missing")
    
    # 强制使用 Tiffany Blue 风格浅色主题
    # Tiffany Blue: #0ABAB5 (标准), #81D8D0 (经典), #E0F2F1 (极浅背景)
    app.setStyleSheet("""
        QWidget {
            background-color: #E0F2F1; /* 极浅的青色背景 */
            color: #004D40; /* 深青色文字 */
            font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        }
        
        /* 分组框 */
        QGroupBox {
            background-color: #ffffff;
            border: 1px solid #80CBC4; /* 浅青色边框 */
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: #00695C; /* 较深的青色标题 */
            font-weight: bold;
            background-color: #E0F2F1; /* 标题背景与主背景一致，制造悬浮感 */
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
            /* image: url(assets/images/home/home_check.png); */
        }

        /* 复选框 */
        QCheckBox {
            spacing: 5px;
            color: #004D40;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #009688; /* 深青色边框，确保可见 */
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

        /* 输入控件 */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #ffffff;
            border: 1px solid #B2DFDB;
            border-radius: 4px;
            padding: 4px;
            color: #004D40;
            selection-background-color: #80CBC4;
        }
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
            border: 1px solid #009688; /* 聚焦时颜色加深 */
        }

        /* 列表与文本域 */
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

        /* 按钮 */
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
        
        /* 特殊按钮：开始/停止 (通过 objectName 或 property 区分更好，这里先通用) */
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

        /* 滚动区域 */
        QScrollArea {
            background-color: transparent;
            border: none;
        }
        
        /* 滚动条 */
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

        /* 折叠框按钮 (CollapsibleBox) */
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
    
    logger.info("KSAS UI Launched.")
    sys.exit(app.exec())