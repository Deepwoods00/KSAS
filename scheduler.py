# -*- coding: utf-8 -*-
import time
import logging
import threading
from datetime import datetime, timedelta
from PySide6.QtCore import QThread, Signal

# 引入日志桥梁
from logging_setup import GuiLogHandler, setup_file_logging
# 引入异常
from basic import TaskInterruptedError

class InstanceScheduler(QThread):
    """
    ALAS 风格的智能调度器 (优化版)
    
    特性：
    1. 任务调度：原子执行 + 循环扫描。
    2. 体力回复：独立倒计时逻辑 (5分钟回1点)，不受任务打断。
    """
    
    def __init__(self, instance_id, device, data, task_classes):
        super().__init__()
        self.instance_id = instance_id
        self.device = device
        self.data = data
        
        self.logger = logging.getLogger(f"{instance_id}.Scheduler")
        
        # 1. 挂载日志桥梁 (UI显示)
        self.instance_root_logger = logging.getLogger(instance_id)
        self.instance_root_logger.setLevel(logging.INFO)
        self.gui_handler = GuiLogHandler(data)
        self.instance_root_logger.addHandler(self.gui_handler)
        
        # 2. 挂载文件日志 (文件存储)
        import os
        log_dir = os.path.join(data.base_dir, "log")
        self.file_handler = setup_file_logging(instance_id, log_dir)

        self._is_running = False
        
        # 3. 智能闹钟 (Event)
        self._wake_event = threading.Event()

        # 4. ⏳ 独立体力计时器 (Next Stamina Tick)
        # 存储下一次回复体力的绝对时间 (datetime 对象)
        # 初始化为 None，表示闹钟目前是关着的
        self._next_stamina_tick = None
        
        # 5. 信号连接
        self.data.sig_config_changed.connect(self.on_config_changed)
        self.data.sig_stats_updated.connect(self.on_stat_changed)

        # 6. 装载任务实例
        self.tasks = []
        for TaskCls in task_classes:
            try:
                task_obj = TaskCls(device, data)
                self.tasks.append(task_obj)
            except Exception as e:
                self.logger.error(f"任务 {TaskCls.__name__} 初始化失败: {e}")

        # 7. 绑定中断回调 (直接绑定到当前实例的方法)
        self.device.interrupt_callback = self._check_interrupt

    def _check_interrupt(self):
        """
        检查是否应该中断设备操作
        返回 True 表示需要中断
        """
        # 如果调度器不在运行状态，则中断
        return not self._is_running

    # ==========================================
    # 📡 信号处理
    # ==========================================
    
    def on_config_changed(self, key, value):
        """配置变更：立即唤醒"""
        if self._is_running:
            self._wake_event.set()

    def on_stat_changed(self, key, value):
        """任务时间变更：立即唤醒"""
        if self._is_running and "next_run" in key:
            self._wake_event.set()

    # ==========================================
    # 🎮 控制接口
    # ==========================================
    
    @property
    def is_running_flag(self):
        """对外暴露的运行状态标志"""
        # self.logger.debug(f"Checking is_running_flag: {self._is_running}")
        return self._is_running

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
            self._wake_event.set() # 唤醒退出
            self.logger.info("正在停止调度器...")
            self.wait()
            
            self.instance_root_logger.removeHandler(self.gui_handler)
            self.logger.info("调度器已停止")

    # ==========================================
    # 🔄 核心循环 (大脑)
    # ==========================================

    def run(self):
        self.logger.info("调度器线程已启动")
        
        # 1. 飞行前安检
        if not self.device.connect():
            self.logger.error("❌ 无法连接设备，调度器自动停止。")
            self.data.set_runtime("is_running", False)
            return

        # 🏠 启动时先尝试回到首页 (初始化状态)
        try:
            self.logger.info("正在初始化游戏状态 (回到首页)...")
            self.device.ensure_home()
        except Exception as e:
            self.logger.warning(f"初始化回城失败: {e} (将尝试继续运行)")

        while self._is_running:
            self._wake_event.clear()
            now = datetime.now()
            
            # ==========================================
            # 🟢 模块一：体力自动回复逻辑 (独立倒计时)
            # ==========================================
            current_stamina = self.data.get_stat("stamina", 0)
            
            if current_stamina >= 200:
                # 满体力：关闭闹钟
                self._next_stamina_tick = None
            else:
                # 不满体力：检查闹钟
                if self._next_stamina_tick is None:
                    # 如果闹钟没开，现在立刻开启 (当前时间 + 300秒)
                    self._next_stamina_tick = now + timedelta(seconds=300)
                    # self.logger.debug(f"体力不满，开始回复计时 (下次: {self._next_stamina_tick.strftime('%H:%M:%S')})")
                
                # 检查时间是否到了
                if now >= self._next_stamina_tick:
                    # 时间到！体力+1
                    new_val = current_stamina + 1
                    self.data.set_stat("stamina", new_val)
                    self.logger.info(f"💧 体力自然回复 +1 (当前: {new_val})")
                    
                    # 闹钟往后顺延 300秒 (保持节奏)
                    self._next_stamina_tick += timedelta(seconds=300)
                    
                    # 防御性编程：如果休眠太久(比如关机了)，tick 时间远远落后于 now，就重置为 now+300
                    if self._next_stamina_tick < now:
                         self._next_stamina_tick = now + timedelta(seconds=300)

            # ==========================================
            # 🟡 模块二：任务扫描逻辑
            # ==========================================
            ready_tasks = []
            next_task_time = None 

            for task in self.tasks:
                if not task.enabled:
                    continue 
                
                if now >= task.next_run:
                    ready_tasks.append(task)
                else:
                    # 记录最近的一个未来任务时间
                    if next_task_time is None or task.next_run < next_task_time:
                        next_task_time = task.next_run

            # ==========================================
            # 🔵 模块三：决策与执行
            # ==========================================
            if ready_tasks:
                # A. 有任务：按优先级执行
                ready_tasks.sort(key=lambda t: t.priority)
                winner = ready_tasks[0]
                
                self.data.set_runtime("current_task", winner.name)
                
                try:
                    winner.execute()
                except TaskInterruptedError:
                    self.logger.warning(f"🛑 任务 {winner.name} 被用户强制中断！")
                    self.data.set_runtime("current_task", "Interrupted")
                    
                    # 🏠 中断后尝试回到首页 (善后处理)
                    # 必须先临时禁用中断回调，否则 ensure_home 里的点击操作也会被立刻中断
                    original_callback = self.device.interrupt_callback
                    self.device.interrupt_callback = None
                    
                    try:
                        self.logger.info("正在尝试回到首页...")
                        self.device.ensure_home()
                    except Exception as e:
                        self.logger.error(f"回城失败: {e}")
                    finally:
                        # 恢复回调 (虽然线程马上要退出了，但保持状态一致性是个好习惯)
                        self.device.interrupt_callback = original_callback

                    # 中断后不需要 continue，直接让 while 循环去判断 self._is_running 即可
                
                # 跑完立即进入下一次循环 (不 sleep)，以便快速响应
                continue
            
            else:
                # B. 没任务：计算休眠时间
                # 我们需要同时考虑 "下个任务的时间" 和 "下个体力的时间"
                # 谁先到，就睡到谁那个时候醒
                
                wait_seconds = 3600 # 默认睡很久
                status_msg = "无任务，待机中..."

                # 1. 考虑任务
                if next_task_time:
                    delta_task = (next_task_time - now).total_seconds()
                    wait_seconds = min(wait_seconds, delta_task)
                    status_msg = f"休眠 (任务 {int(delta_task)}s 后)"

                # 2. 考虑体力 (为了准时加体力，不能睡过头)
                if self._next_stamina_tick:
                    delta_stamina = (self._next_stamina_tick - now).total_seconds()
                    # 至少睡 0.1 秒防止 CPU 空转
                    delta_stamina = max(0.1, delta_stamina)
                    wait_seconds = min(wait_seconds, delta_stamina)
                    # 如果体力马上就要回了，状态栏也可以显示一下
                    if delta_stamina < wait_seconds: 
                        status_msg = f"休眠 (回体 {int(delta_stamina)}s 后)"

                # 确保至少睡一点点，防止逻辑死循环跑太快
                wait_seconds = max(0.5, wait_seconds)
                
                self.data.set_runtime("current_task", status_msg)
                
                # 智能休眠
                self._wake_event.wait(wait_seconds)