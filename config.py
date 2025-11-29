# -*- coding: utf-8 -*-
import os
import json
import logging

class GlobalConfig:
    _instance = None
    
    DEFAULT_CONFIG = {
        "language": "zh_CN",
        "close_to_tray": False,   # 默认关闭：点击关闭按钮直接退出
        "auto_connect": True,    # 启动时自动连接
        "adb_path": "",          # 自定义 ADB 路径
        "use_internal_adb": True, # 是否使用内置 ADB
        "license_key": ""        # KeyAuth 卡密
    }

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(GlobalConfig, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, config_path="config.json"):
        if hasattr(self, "_initialized"):
            return
        self.config_path = config_path
        self.config = self.DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger("GlobalConfig")
        self.load()
        self._initialized = True

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 合并配置，确保新字段存在
                    for key, val in data.items():
                        self.config[key] = val
            except Exception as e:
                self.logger.error(f"加载全局配置失败: {e}")

    def save(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存全局配置失败: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

# 全局单例
global_config = GlobalConfig()
