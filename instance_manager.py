# -*- coding: utf-8 -*-
# instance_manager.py
import os
import json
import logging
import re
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal

# 引入 DataStore
from datastore import InstanceDataStore
# 引入 ADB
from airtest.core.android.adb import ADB
# 引入 Scheduler 和 任务列表
from scheduler import InstanceScheduler
from task_registry import get_all_tasks
# 引入 DeviceOperator
from basic import DeviceOperator

class InstanceManager(QObject):
    """
    实例管理器
    """
    sig_instance_list_changed = Signal()

    def __init__(self, data_root="data"):
        super().__init__()
        self.data_root = data_root
        self.registry_path = os.path.join(data_root, "device_registry.json")
        self.logger = logging.getLogger("InstanceManager")

        # 核心容器
        self.data_stores = {} 
        self.schedulers = {}  # <--- 【关键修复】这里必须初始化！
        
        self._registry = {}

        # 初始化
        self._load_registry()
        self._init_all_instances()

    # ===========================================
    # 📂 初始化与加载
    # ===========================================
    def _load_registry(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self._registry = json.loads(content)
                    else:
                        self._registry = {}
            except Exception as e:
                self.logger.error(f"注册表损坏: {e}")
                self._registry = {}
        else:
            self._registry = {}

    def _save_registry(self):
        try:
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(self._registry, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存注册表失败: {e}")

    def _init_all_instances(self):
        """启动时加载所有已注册账号"""
        task_classes = get_all_tasks()

        for instance_id, info in self._registry.items():
            self.logger.info(f"正在加载实例: {info.get('display_name')} ({instance_id})")
            
            # 1. 加载 DataStore
            store = InstanceDataStore(instance_id, self.data_root)
            self.data_stores[instance_id] = store
            
            # 2. 加载 Scheduler
            try:
                device = DeviceOperator(info['serial'], instance_id)
                sched = InstanceScheduler(instance_id, device, store, task_classes)
                self.schedulers[instance_id] = sched
            except Exception as e:
                self.logger.error(f"加载调度器失败 {instance_id}: {e}")

    # ===========================================
    # 🆕 核心创建逻辑 (修复版)
    # ===========================================
    def create_instance(self, display_name, serial):
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', display_name).lower()
        instance_id = safe_name
        counter = 1
        while instance_id in self._registry:
            instance_id = f"{safe_name}_{counter}"
            counter += 1

        try:
            # 1. 写入注册表
            self._registry[instance_id] = {
                "display_name": display_name,
                "serial": serial,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_registry()

            # 2. 创建 DataStore
            new_store = InstanceDataStore(instance_id, self.data_root)
            new_store.set_cfg("meta.serial", serial)
            new_store.set_cfg("meta.alias", display_name)
            self.data_stores[instance_id] = new_store

            # 3. 创建 Scheduler
            device = DeviceOperator(serial, instance_id)
            task_classes = get_all_tasks()
            
            sched = InstanceScheduler(instance_id, device, new_store, task_classes)
            self.schedulers[instance_id] = sched  # <--- 这里现在安全了

            self.logger.info(f"新实例创建成功: {display_name}")
            self.sig_instance_list_changed.emit()
            return True, instance_id

        except Exception as e:
            self.logger.error(f"创建实例失败: {e}")
            if instance_id in self._registry:
                del self._registry[instance_id]
            return False, str(e)

    # ===========================================
    # 其他辅助方法
    # ===========================================
    def delete_instance(self, instance_id):
        if instance_id not in self._registry:
            return
        
        # 停止并删除 Scheduler
        if instance_id in self.schedulers:
            self.schedulers[instance_id].stop_scheduler()
            del self.schedulers[instance_id]

        if instance_id in self.data_stores:
            del self.data_stores[instance_id]

        del self._registry[instance_id]
        self._save_registry()
        self.sig_instance_list_changed.emit()

    def get_all_instances(self):
        result = []
        for iid, info in self._registry.items():
            store = self.data_stores.get(iid)
            status = store.get_runtime("connect_status", "OFFLINE") if store else "ERROR"
            result.append({
                "id": iid,
                "name": info["display_name"],
                "serial": info["serial"],
                "status": status
            })
        return result

    def get_store(self, instance_id):
        return self.data_stores.get(instance_id)
    
    def get_scheduler(self, instance_id):
        return self.schedulers.get(instance_id)

    # 手动添加入口
    def add_instance_by_ip(self, display_name, ip_address):
        # ... (保持之前的代码，此处省略以节省篇幅) ...
        pass