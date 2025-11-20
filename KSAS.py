# -*- coding: utf-8 -*-
import sys
import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["PADDLE_NUM_THREADS"] = "2"
os.environ["OPENCV_NUM_THREADS"] = "2"
import logging
from PySide6.QtWidgets import QApplication
from ui.main_window_logic import MainWindowLogic

# =========== 👇 引入配置和 Airtest ADB 类 👇 ===========
from config import global_config
from airtest.core.android.adb import ADB

# 用于存储我们要强制使用的路径
_TARGET_ADB_PATH = None

def setup_global_adb():
    """
    使用 Monkey Patch (移花接木) 技术，强制替换 Airtest 的 ADB 路径
    """
    global _TARGET_ADB_PATH
    
    # 1. 读取配置，找到真正的 adb.exe
    use_internal = global_config.get("use_internal_adb", True)
    custom_path = global_config.get("adb_path", "")
    
    if use_internal:
        internal_path = os.path.join(os.getcwd(), "tools", "adb", "adb.exe")
        if os.path.exists(internal_path):
            _TARGET_ADB_PATH = internal_path
    else:
        if custom_path and os.path.exists(custom_path):
            _TARGET_ADB_PATH = custom_path
            
    if not _TARGET_ADB_PATH:
        print("⚠️ [System] 未找到指定 ADB，将使用系统默认")
        return

    print(f"✅ [System] 全局 ADB 路径已锁定: {_TARGET_ADB_PATH}")

    # 2. 【黑魔法】保存原版的构造函数
    _original_init = ADB.__init__

    # 3. 【黑魔法】定义一个新的构造函数
    def _patched_init(self, serialno=None, adb_path=None, server_addr=None, **kwargs):
        # 关键点：如果调用时没指定 path，或者指定的是默认的，我们强行替换成我们的
        if not adb_path:
            adb_path = _TARGET_ADB_PATH
            
        # 调用原版逻辑，但传入了我们的 path
        _original_init(self, serialno=serialno, adb_path=adb_path, server_addr=server_addr, **kwargs)

    # 4. 【黑魔法】把 Airtest 的构造函数换成我们的
    ADB.__init__ = _patched_init
# ======================================================

# 配置日志输出格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Main")

if __name__ == "__main__":
    # 1. 先施展魔法 (必须在其他逻辑开始前)
    setup_global_adb()

    # 2. 创建 Qt App
    app = QApplication(sys.argv)
    
    # 3. 创建主窗口逻辑
    window = MainWindowLogic()
    window.show()
    
    logger.info("KSAS UI Launched.")
    
    # 4. 进入事件循环
    sys.exit(app.exec())