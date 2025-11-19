# -*- coding: utf-8 -*-
import sys
import logging
from PySide6.QtWidgets import QApplication
from ui.main_window_logic import MainWindowLogic

# 配置日志输出格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Main")

if __name__ == "__main__":
    # 1. 创建 Qt App
    app = QApplication(sys.argv)
    
    # 2. 创建主窗口逻辑
    window = MainWindowLogic()
    window.show()
    
    logger.info("KSAS V3.4 UI Launched.")
    
    # 3. 进入事件循环
    sys.exit(app.exec())