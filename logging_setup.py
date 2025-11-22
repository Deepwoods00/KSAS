# logging_setup.py
# -*- coding: utf-8 -*-
import logging
import os
# 👇 引入轮转文件处理器
from logging.handlers import RotatingFileHandler

class GuiLogHandler(logging.Handler):
    """
    自定义日志处理器：拦截日志并转发给 DataStore -> UI
    """
    def __init__(self, datastore):
        super().__init__()
        self.datastore = datastore
        self.instance_id = datastore.instance_id
        # 设置格式: 只取消息内容
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        """
        当有日志产生时触发
        """
        try:
            msg = self.format(record)
            level = record.levelname
            # 拼装 ID，防止 UI 串台
            full_msg = f"{self.instance_id}|||{msg}"
            self.datastore.push_log(full_msg, level)
        except Exception:
            self.handleError(record)

def setup_file_logging(instance_id, log_dir):
    """
    给指定实例挂载文件日志功能 (带自动切割功能)
    :return: Handler 对象
    """
    logger = logging.getLogger(instance_id)
    logger.setLevel(logging.INFO)
    
    # 1. 检查是否已经有文件处理器了 (防止重复添加)
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler):
            return h

    # 2. 确保目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 3. 创建轮转文件处理器 (核心修改)
    log_path = os.path.join(log_dir, "ksas.log")
    
    # maxBytes=2*1024*1024 (2MB)
    # backupCount=3 (最多保留3个旧文件，比如 ksas.log.1, ksas.log.2)
    file_handler = RotatingFileHandler(
        log_path, 
        mode='a', 
        maxBytes=2*1024*1024, 
        backupCount=3, 
        encoding='utf-8'
    )
    
    # 4. 设置格式
    formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 5. 挂载
    logger.addHandler(file_handler)
    
    return file_handler