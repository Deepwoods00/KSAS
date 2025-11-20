# -*- coding: utf-8 -*-
import time
import logging
import threading
from datetime import datetime
from PySide6.QtCore import QThread, Signal

# 引入日志桥梁
from logging_setup import GuiLogHandler, setup_file_logging

class InstanceScheduler(QThread):
    """
    ALAS 风格的智能调度器 (Event-Driven Timeline Scheduler)
    
    特点：
    1. 基于时间轴 (Next Run) 调度，而非死循环轮询。
    2. 支持事件唤醒 (Config/NextRun 变更立即响应)。
    3. 自动过滤无关信号 (体力变化不吵醒线程)。
    4. 集成日志桥梁，将后台日志转发给 UI。
    """
    
    # 信号：向 UI 发送日志 (Level, Message)
    # 注意：有了 GuiLogHandler 后，这个信号主要由 Handler 触发，
    # 但保留在这里作为备用或直接调用接口。
    sig_log = Signal(str, str)

    def __init__(self, instance_id, device, data, task_classes):
        """
        :param task_classes: 任务类列表 [HuntingTask, GatheringTask...]
        """
        super().__init__()
        self.instance_id = instance_id
        self.device = device
        self.data = data
        
        # 1. 规范化 Logger 命名: "实例ID.模块"
        # 这样 logging_setup 里的过滤器就能按实例ID拦截日志
        self.logger = logging.getLogger(f"{instance_id}.Scheduler")
        
        # 2. 挂载日志桥梁 (Rainbow Bridge)
        # 监听属于该实例的所有日志
        self.instance_root_logger = logging.getLogger(instance_id)
        self.instance_root_logger.setLevel(logging.INFO)
        self.gui_handler = GuiLogHandler(data)
        self.instance_root_logger.addHandler(self.gui_handler)
        
        import os
        log_dir = os.path.join(data.base_dir, "log")
        
        # 2. 调用 logging_setup.py 里的函数，把它挂上去
        self.file_handler = setup_file_logging(instance_id, log_dir)

        self._is_running = False
        
        # 3. 核心组件：智能闹钟
        self._wake_event = threading.Event()
        
        # 4. 信号连接
        # 配置变了 -> 必须醒
        self.data.sig_config_changed.connect(self.on_config_changed)
        # 数据变了 (next_run 清空了) -> 必须醒
        self.data.sig_stats_updated.connect(self.on_stat_changed)

        # 5. 装载任务实例
        self.tasks = []
        for TaskCls in task_classes:
            try:
                task_obj = TaskCls(device, data)
                self.tasks.append(task_obj)
            except Exception as e:
                self.logger.error(f"任务 {TaskCls} 初始化失败: {e}")

    # ==========================================
    # 📡 信号处理 (过滤网)
    # ==========================================
    
    def on_config_changed(self, key, value):
        """配置变更：无条件唤醒"""
        if self._is_running:
            self.logger.debug(f"配置变更 [{key}]，唤醒调度器")
            self._wake_event.set()

    def on_stat_changed(self, key, value):
        """
        数据变更：【关键过滤】
        只有当变动的是 'next_run' 时才唤醒。
        """
        if self._is_running and "next_run" in key:
            self.logger.info(f"任务计划变更 [{key}]，立即唤醒调度器")
            self._wake_event.set()

    # ==========================================
    # 🎮 控制接口
    # ==========================================

    def start_scheduler(self):
        if not self.isRunning():
            self._is_running = True
            self.data.set_runtime("is_running", True)
            self._wake_event.clear()
            self.start()
            self.logger.info("调度器已启动")

    def stop_scheduler(self):
        if self.isRunning():
            self._is_running = False
            self.data.set_runtime("is_running", False)
            # 按下闹钟，让它从 wait() 中醒来并退出循环
            self._wake_event.set()
            self.logger.info("正在停止调度器...")
            self.wait() # 等待线程安全退出
            
            # 移除日志桥梁，防止内存泄漏或重复打印
            self.instance_root_logger.removeHandler(self.gui_handler)
            self.instance_root_logger.removeHandler(self.file_handler)
            self.logger.info("调度器已停止")

    # ==========================================
    # 🔄 核心循环 (The Brain)
    # ==========================================

    def run(self):
        self.logger.info("调度器线程已启动")
        
        # =========== 👇 新增：飞行前安检 (Pre-flight Check) 👇 ===========
        self.logger.info("正在检查设备环境...", "INFO")
        
        # 1. 确保连接 (防止连不上)
        if not self.device.connect():
            self.logger.error("❌ 无法连接设备！请检查模拟器是否启动。", "ERROR")
            self.data.set_runtime("is_running", False) # 告诉 UI 我停了
            return # 直接退出线程
            
        # 2. 检查分辨率 (防止点歪)
        if not self.device.check_resolution():
            self.logger.error("❌ 分辨率不匹配！脚本要求: 720x1280 (允许横屏)", "ERROR")
            self.logger.error("请修改模拟器分辨率设置并重启模拟器。", "ERROR")
            self.data.set_runtime("is_running", False) # 告诉 UI 我停了
            return # 直接退出线程
            
        self.logger.info("✅ 环境检查通过，开始调度任务。", "INFO")


        while self._is_running:
            self._wake_event.clear()
            
            now = datetime.now()
            ready_tasks = []
            next_wake_up_time = None 

            # --- 1. 扫描阶段 ---
            for task in self.tasks:
                if not task.enabled:
                    continue 
                
                if now >= task.next_run:
                    ready_tasks.append(task)
                else:
                    if next_wake_up_time is None or task.next_run < next_wake_up_time:
                        next_wake_up_time = task.next_run

            # --- 2. 决策阶段 ---
            if ready_tasks:
                # A. 有活干：按优先级排序
                ready_tasks.sort(key=lambda t: t.priority)
                winner = ready_tasks[0]
                
                self.logger.info(f"开始执行任务: {winner.name}")
                
                # 执行任务
                winner.execute() 
                
                time.sleep(1)
            
            else:
                # B. 没活干：计算休眠时间
                if next_wake_up_time:
                    delta = (next_wake_up_time - now).total_seconds()
                    wait_seconds = max(1, delta)
                    msg = f"休眠中 (下次任务 {int(wait_seconds)}s 后)"
                else:
                    wait_seconds = 3600 
                    msg = "无任务，待机中..."
                
                self.data.set_runtime("current_task", msg)
                self.logger.info(msg) # 打印休眠日志，证明没死机
                
                # --- 3. 智能休眠 ---
                self._wake_event.wait(wait_seconds)
                
                if self._is_running:
                    self.logger.debug("调度器被唤醒/自然醒，重新评估...")