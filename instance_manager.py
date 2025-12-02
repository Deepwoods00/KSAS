# -*- coding: utf-8 -*-
# instance_manager.py
import os
import json
import logging
import re
import time
import shutil
from datetime import datetime
from PySide6.QtCore import QObject, Signal

from datastore import InstanceDataStore
from scheduler import InstanceScheduler
from task_registry import get_all_tasks
from basic import DeviceOperator
from i18n.i18n import get_text

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

        self.data_stores = {} 
        self.schedulers = {} 
        self._registry = {}

        self._load_registry()
        self._init_all_instances()

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
                self.logger.error(get_text("log_registry_corrupted", e))
                self._registry = {}
        else:
            self._registry = {}

    def _save_registry(self):
        try:
            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(self._registry, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(get_text("log_save_registry_failed", e))

    def _init_all_instances(self):
        """启动时加载所有已注册账号"""
        task_classes = get_all_tasks()

        for instance_id, info in self._registry.items():
            self.logger.info(get_text("log_loading_instance", info.get('display_name'), instance_id))
            store = InstanceDataStore(instance_id, self.data_root)
            self.data_stores[instance_id] = store
            
            try:
                device = DeviceOperator(info['serial'], instance_id)
                # device.connect() # 启动时不强制连接，为了速度
                sched = InstanceScheduler(instance_id, device, store, task_classes)
                
                # 🔄 【绑定】设置 DeviceOperator 的中断回调
                # (已移至 Scheduler.__init__ 内部处理，避免闭包引用问题)
                # device.interrupt_callback = lambda: not sched.is_running_flag
                
                self.schedulers[instance_id] = sched
                
                # 🧹 启动自动清理 (异步或同步均可，这里用同步简单处理，因为文件IO通常很快)
                self._cleanup_files(instance_id)
                
            except Exception as e:
                self.logger.error(get_text("log_load_scheduler_failed", instance_id, e))

    def create_instance(self, display_name, serial, diana_level=0, march_slots=5):
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', display_name).lower()
        instance_id = safe_name
        counter = 1
        while instance_id in self._registry:
            instance_id = f"{safe_name}_{counter}"
            counter += 1

        try:
            self._registry[instance_id] = {
                "display_name": display_name,
                "serial": serial,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_registry()

            new_store = InstanceDataStore(instance_id, self.data_root)
            new_store.set_cfg("meta.serial", serial)
            new_store.set_cfg("meta.alias", display_name)
            # 设置 Diana 等级和行军队列
            new_store.set_cfg("modules.general.diana_level", int(diana_level))
            new_store.set_cfg("modules.general.total_march_slots", int(march_slots))
            
            self.data_stores[instance_id] = new_store

            device = DeviceOperator(serial, instance_id)
            device.connect()
            
            task_classes = get_all_tasks()
            sched = InstanceScheduler(instance_id, device, new_store, task_classes)
            
            # 🔄 【绑定】设置中断回调
            # (已移至 Scheduler.__init__ 内部处理)
            # device.interrupt_callback = lambda: not sched.is_running_flag
            
            self.schedulers[instance_id] = sched

            self.logger.info(get_text("log_instance_created", display_name))
            self.sig_instance_list_changed.emit()
            return True, instance_id

        except Exception as e:
            self.logger.error(get_text("log_create_instance_failed", e))
            if instance_id in self._registry:
                del self._registry[instance_id]
            return False, str(e)

    def delete_instance(self, instance_id):
        if instance_id not in self._registry:
            return
        
        self.logger.info(get_text("log_deleting_instance", instance_id))

        if instance_id in self.schedulers:
            try:
                sched = self.schedulers[instance_id]
                if sched.isRunning():
                    sched.stop_scheduler()
                time.sleep(0.1)
            except Exception as e:
                self.logger.error(get_text("log_stop_scheduler_error", e))
            del self.schedulers[instance_id]

        if instance_id in self.data_stores:
            del self.data_stores[instance_id]

        dir_path = os.path.join(self.data_root, instance_id)
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                self.logger.info(get_text("log_folder_deleted", dir_path))
            except Exception as e:
                self.logger.error(get_text("log_delete_failed", e))

        del self._registry[instance_id]
        self._save_registry()
        self.sig_instance_list_changed.emit()

    def update_instance(self, instance_id, new_serial=None, new_alias=None, new_diana_level=None, new_march_slots=None):
        """
        更新实例信息
        """
        if instance_id not in self._registry:
            return False

        # 1. 更新注册表 (只存核心信息)
        if new_serial:
            self._registry[instance_id]['serial'] = new_serial
        if new_alias:
            self._registry[instance_id]['display_name'] = new_alias
        self._save_registry()

        # 2. 更新 DataStore (存配置)
        store = self.data_stores.get(instance_id)
        if store:
            if new_serial:
                store.set_cfg("meta.serial", new_serial)
                if instance_id in self.schedulers:
                    self.schedulers[instance_id].device.serial = new_serial
            if new_alias:
                store.set_cfg("meta.alias", new_alias)
            
            # 👇 【新增】保存 Diana 等级
            if new_diana_level is not None:
                store.set_cfg("modules.general.diana_level", int(new_diana_level))

            # 👇 【新增】保存行军队列数量
            if new_march_slots is not None:
                store.set_cfg("modules.general.total_march_slots", int(new_march_slots))
        
        self.logger.info(get_text("log_instance_conf_updated", instance_id))
        self.sig_instance_list_changed.emit()
        return True

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

    def _cleanup_files(self, instance_id):
        """清理过期日志和截图 (保留7天)"""
        try:
            base_dir = os.path.join(self.data_root, instance_id)
            targets = [
                os.path.join(base_dir, "log"),
                os.path.join(base_dir, "snapshots")
            ]
            
            now = time.time()
            retention_days = 7
            retention_sec = retention_days * 86400
            
            for folder in targets:
                if not os.path.exists(folder):
                    continue
                    
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    # 仅处理文件
                    if os.path.isfile(file_path):
                        # 获取修改时间
                        mtime = os.path.getmtime(file_path)
                        if now - mtime > retention_sec:
                            try:
                                os.remove(file_path)
                                self.logger.info(get_text("log_cleanup_file", instance_id, filename))
                            except Exception as del_err:
                                self.logger.warning(get_text("log_cleanup_file_failed", filename, del_err))
        except Exception as e:
            self.logger.error(get_text("log_cleanup_error", instance_id, e))