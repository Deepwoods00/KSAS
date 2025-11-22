# -*- coding: utf-8 -*-
import os
import json
import threading
import logging
from PySide6.QtCore import QObject, Signal

class InstanceDataStore(QObject):
    """
    单个实例的数据管家 (Per-Instance Data Manager)
    
    职责：
    1. 管理 config.json (用户配置：读多写少)
    2. 管理 statistics.json (游戏数据：写多读少)
    3. 维护 runtime memory (内存状态：不存盘)
    4. 作为 UI 和 后台脚本 的通讯枢纽 (Signals)
    """

    # ==================================================
    # 📡 信号定义 (Signals for UI)
    # ==================================================
    
    # 1. 配置变更信号: (key_path, new_value)
    # 场景：代码里重置了配置 -> UI 复选框自动更新
    sig_config_changed = Signal(str, object)

    # 2. 统计/资源数据变更信号: (key_path, new_value)
    # 场景：脚本 OCR 读到了新体力 -> UI 进度条刷新
    sig_stats_updated = Signal(str, object)

    # 3. 运行时状态变更信号: (key, new_value)
    # 场景：ADB 断开连接 -> UI 状态灯变红
    sig_runtime_changed = Signal(str, object)

    # 4. 日志信号: (level, message)
    # 场景：把后台的 print/log 转发到 UI 的文本框里
    sig_log_msg = Signal(str, str)

    def __init__(self, instance_id, data_root="data"):
        super().__init__()
        self.instance_id = instance_id
        
        # --- 路径配置 ---
        # 你的结构: data/deep_sl_002/
        self.base_dir = os.path.join(data_root, instance_id)
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.stats_path = os.path.join(self.base_dir, "statistics.json")

        # --- 线程安全锁 ---
        # RLock (可重入锁) 允许同一个线程多次获得锁，防止死锁
        self._lock = threading.RLock()

        # --- 内存数据容器 ---
        self._config = {}   # 对应 config.json
        self._stats = {}    # 对应 statistics.json
        self._runtime = {   # 纯内存状态 (关机即焚)
            "is_running": False,       # 调度器运行状态
            "connect_status": "OFFLINE", # ADB 连接状态
            "current_task": "Idle"     # 当前正在执行的任务名
        }

        # --- 初始化 ---
        self._ensure_dirs()
        self.load_all()

    def _ensure_dirs(self):
        """确保专属文件夹及子文件夹结构完整"""
        # 1. 创建实例主目录 (data/deep_sl_002)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)
            
        # 2. 创建日志目录 (data/deep_sl_002/log)
        log_dir = os.path.join(self.base_dir, "log")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 3. 创建截图目录 (data/deep_sl_002/snapshots)
        snap_dir = os.path.join(self.base_dir, "snapshots")
        if not os.path.exists(snap_dir):
            os.makedirs(snap_dir, exist_ok=True)

    def load_all(self):
        """加载所有持久化数据"""
        # 1. 加载配置 (带默认值)
        default_config = self._load_default_json("data/defaults/default_config.json")
        if default_config:
            # 动态设置 instance_name 默认值
            default_config["instance_name"] = self.instance_id
        else:
            # Fallback if file missing
            default_config = {"instance_name": self.instance_id}
            
        self._load_json(self.config_path, self._config, default_config)

        # 2. 加载统计 (默认为空)
        default_stats = self._load_default_json("data/defaults/default_statistics.json")
        if not default_stats:
             default_stats = {}
             
        self._load_json(self.stats_path, self._stats, default_stats)

    def _load_default_json(self, path):
        """从模板文件加载默认配置"""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading default json {path}: {e}")
        return None

    def _load_json(self, path, container, default):
        """通用的安全读取逻辑 (带简单的二级补全)"""
        with self._lock:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        saved_data = json.load(f)
                        
                        # 1. 先把默认值深拷贝进来
                        # (这样能保证拥有最全的字段结构)
                        import copy
                        merged_data = copy.deepcopy(default)
                        
                        # 2. 递归更新 (这里只做两层简单的合并，够用了)
                        for key, val in saved_data.items():
                            if isinstance(val, dict) and key in merged_data and isinstance(merged_data[key], dict):
                                # 如果是字典（比如 modules），进去更新里面的字段
                                merged_data[key].update(val)
                            else:
                                # 如果是普通值，直接覆盖
                                merged_data[key] = val
                        
                        # 3. 更新到内存容器
                        container.clear()
                        container.update(merged_data)
                        
                except Exception as e:
                    self.push_log(f"文件 {os.path.basename(path)} 损坏/解析失败: {e}", "ERROR")
                    # 损坏了就用默认值
                    container.clear()
                    container.update(default)
                    self._save_json(path, container)
            else:
                # 文件不存在，初始化为默认值
                container.update(default)
                self._save_json(path, container)

    def _save_json(self, path, container):
        """通用的安全保存逻辑"""
        with self._lock:
            try:
                # 临时写入再重命名，防止写入一半断电导致文件损坏 (Atomic Write 思想)
                temp_path = path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(container, f, indent=4, ensure_ascii=False)
                
                if os.path.exists(path):
                    os.remove(path)
                os.rename(temp_path, path)
            except Exception as e:
                self.push_log(f"保存 {os.path.basename(path)} 失败: {e}", "ERROR")

    def save_config(self):
        """手动触发保存配置"""
        self._save_json(self.config_path, self._config)

    def save_stats(self):
        """手动触发保存统计"""
        self._save_json(self.stats_path, self._stats)

    # ==================================================
    # 🔧 数据操作接口 (Getters & Setters)
    # ==================================================

    # --- 1. 用户配置 (Config) ---
    
    def get_cfg(self, key_path, default=None):
        """
        读取配置
        用法: get_cfg("modules.hunting.enable")
        """
        return self._get_value_by_path(self._config, key_path, default)

    def set_cfg(self, key_path, value):
        """
        修改配置 -> 立即保存 -> 通知 UI
        用法: set_cfg("modules.hunting.enable", True)
        """
        # 如果值确实改变了
        if self._set_value_by_path(self._config, key_path, value):
            self.save_config() # 持久化
            self.sig_config_changed.emit(key_path, value) # 通知 UI

    # --- 2. 游戏数据 (Statistics) ---
    
    def get_stat(self, key_path, default=0):
        """
        读取游戏统计
        用法: get_stat("resources.wood")
        """
        return self._get_value_by_path(self._stats, key_path, default)

    def set_stat(self, key_path, value):
        """
        修改游戏数据 -> 立即保存 -> 通知 UI
        用法: set_stat("stamina", 80)
        """
        if self._set_value_by_path(self._stats, key_path, value):
            self.save_stats() # 持久化
            self.sig_stats_updated.emit(key_path, value) # 通知 UI

    # --- 3. 运行时状态 (Runtime Memory) ---

    def get_runtime(self, key, default=None):
        """读取内存状态"""
        with self._lock:
            return self._runtime.get(key, default)

    def set_runtime(self, key, value):
        """
        修改运行时状态 -> 仅内存 -> 通知 UI
        用法: set_runtime("connect_status", "ONLINE")
        """
        with self._lock:
            if self._runtime.get(key) != value:
                self._runtime[key] = value
                self.sig_runtime_changed.emit(key, value) # 通知 UI

    # ==================================================
    # 🔨 辅助工具 (Helpers)
    # ==================================================

    def push_log(self, message, level="INFO"):
        """
        发送日志信号 (给 UI 显示用)
        并不负责写 log 文件 (写文件由 logging 模块在别处处理)
        """
        self.sig_log_msg.emit(level, message)

    def _get_value_by_path(self, root_dict, path, default):
        """
        [内部工具] 解析点号路径: 'a.b.c' -> dict['a']['b']['c']
        """
        keys = path.split('.')
        data = root_dict
        with self._lock:
            try:
                for k in keys:
                    data = data[k]
                return data
            except (KeyError, TypeError):
                return default

    def _set_value_by_path(self, root_dict, path, value):
        """
        [内部工具] 设置点号路径: 'a.b.c' = value
        返回 True 表示值发生了变化 (需要保存/刷新)
        返回 False 表示值没变 (节省 IO)
        """
        keys = path.split('.')
        data = root_dict
        with self._lock:
            try:
                # 递归找到倒数第二层
                for k in keys[:-1]:
                    # 如果中间层不存在，自动创建空字典
                    data = data.setdefault(k, {})
                
                last_key = keys[-1]
                old_value = data.get(last_key)
                
                if old_value != value:
                    data[last_key] = value
                    return True # 变了
                return False # 没变
            except Exception as e:
                print(f"设置键值失败 {path}: {e}")
                return False

# 文件结束