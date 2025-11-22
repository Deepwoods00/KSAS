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
    window = MainWindowLogic()
    window.show()
    
    logger.info("KSAS UI Launched.")
    sys.exit(app.exec())