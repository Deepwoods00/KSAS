# -*- coding: utf-8 -*-
import time
import logging
import threading
from datetime import datetime
from PySide6.QtCore import QThread, Signal

class InstanceScheduler(QThread):
    """
    ALAS 风格的智能调度器 (Event-Driven Timeline Scheduler)
    
    特点：
    1. 基于时间轴 (Next Run) 调度，而非死循环轮询。
    2. 支持事件唤醒 (Config/NextRun 变更立即响应)。
    3. 自动过滤无关信号 (体力变化不吵醒线程)。
    """
    
    # 信号：向 UI 发送日志 (Level, Message)
    sig_log = Signal(str, str)

    def __init__(self, instance_id, device, data, task_classes):
        """
        :param task_classes: 任务类列表 [HuntingTask, GatheringTask...]
        """
        super().__init__()
        self.instance_id = instance_id
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"Sched_{instance_id}")
        
        self._is_running = False
        
        # ⏰ 核心组件：智能闹钟
        # 用于在休眠时被外部信号瞬间唤醒
        self._wake_event = threading.Event()
        
        # 🔗 信号连接
        # 1. 配置变了 (interval 变了) -> 必须醒
        self.data.sig_config_changed.connect(self.on_config_changed)
        # 2. 数据变了 (next_run 清空了) -> 必须醒
        self.data.sig_stats_updated.connect(self.on_stat_changed)

        # 装载任务实例
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
        只有当变动的是 'next_run' 时才唤醒，防止体力/资源变化导致 CPU 空转。
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
            # 按下闹钟，防止线程在 wait() 中卡死，让它赶紧结束 run() 循环
            self._wake_event.set()
            self.logger.info("正在停止调度器...")
            self.wait() # 等待线程安全退出
            self.logger.info("调度器已停止")

    # ==========================================
    # 🔄 核心循环 (The Brain)
    # ==========================================

    def run(self):
        while self._is_running:
            # 每次循环开始，先重置闹钟
            self._wake_event.clear()
            
            now = datetime.now()
            ready_tasks = []
            next_wake_up_time = None 

            # --- 1. 扫描阶段 ---
            for task in self.tasks:
                if not task.enabled:
                    continue 
                
                # 检查时间
                if now >= task.next_run:
                    ready_tasks.append(task)
                else:
                    # 记录最小的未来时间
                    if next_wake_up_time is None or task.next_run < next_wake_up_time:
                        next_wake_up_time = task.next_run

            # --- 2. 决策阶段 ---
            if ready_tasks:
                # A. 有活干：按优先级排序 (数值越小越优先)
                ready_tasks.sort(key=lambda t: t.priority)
                winner = ready_tasks[0]
                
                self.logger.info(f"开始执行任务: {winner.name}")
                
                # 执行任务 (阻塞直到完成)
                # execute() 内部会自动更新 next_run
                winner.execute() 
                
                # 跑完歇一小会儿，防止连续任务占用过高
                time.sleep(1)
            
            else:
                # B. 没活干：计算休眠时间
                if next_wake_up_time:
                    delta = (next_wake_up_time - now).total_seconds()
                    wait_seconds = max(1, delta)
                    msg = f"休眠中 (下次任务 {int(wait_seconds)}s 后)"
                else:
                    # 所有任务都关了，或者没任务，睡个保底时间
                    wait_seconds = 3600 
                    msg = "无任务，待机中..."
                
                self.data.set_runtime("current_task", msg)
                
                # --- 3. 智能休眠 (Smart Sleep) ---
                # 这里的 wait() 会阻塞，直到：
                # 1. 时间到了 (自然醒)
                # 2. _wake_event.set() 被外部信号调用了 (惊醒)
                self._wake_event.wait(wait_seconds)
                
                if self._is_running:
                    self.logger.debug("调度器被唤醒/自然醒，重新评估...")