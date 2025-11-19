# tasks/base_task.py
# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

class BaseTask:
    """
    所有任务的基类 (ALAS 风格)
    
    核心属性：
    1. name: 任务名 (用于在 JSON 里查找配置)
    2. priority: 优先级 (数字越大越重要，或者越小越重要，这里我们定：数字越小优先级越高 1 > 10)
    3. default_interval: 默认间隔秒数 (如果 config 没填就用这个)
    """
    
    def __init__(self, device, data):
        """
        :param device: basic.py 的 DeviceOperator
        :param data: datastore.py 的 InstanceDataStore
        """
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"Task_{self.name}")

    # ==========================================
    # ⚙️ 子类必须重写/配置的属性
    # ==========================================
    @property
    def name(self):
        return "BaseTask"

    @property
    def priority(self):
        """优先级：1 (最高/紧急) ~ 100 (低/闲时)"""
        return 50

    @property
    def default_interval(self):
        """默认循环间隔 (秒)，默认 1 小时"""
        return 3600

    # ==========================================
    # ⏱️ ALAS 核心调度逻辑 (Scheduler 会调用这些)
    # ==========================================
    
    @property
    def enabled(self):
        """检查用户是否在 UI 上开启了这个任务"""
        # 读取 config.json: modules.hunting.enable
        return self.data.get_cfg(f"modules.{self.name.lower()}.enable", False)

    @property
    def next_run(self):
        """
        从 DataStore 读取下次运行时间
        :return: datetime 对象
        """
        # 读取 statistics.json: tasks.Hunting.next_run
        # 格式是字符串 "2023-11-19 12:00:00"
        time_str = self.data.get_stat(f"tasks.{self.name}.next_run", "1970-01-01 00:00:00")
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.min # 如果格式错，立即执行

    def set_next_run(self, seconds=None):
        """
        设置下次运行时间
        :param seconds: 多少秒后运行。如果不填，尝试去 config 读取 'interval'
        """
        if seconds is None:
            # 尝试从配置读取用户设定的间隔，没有则用默认
            seconds = self.data.get_cfg(f"modules.{self.name.lower()}.interval", self.default_interval)
        
        future_time = datetime.now() + timedelta(seconds=int(seconds))
        time_str = future_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存进 statistics.json (这就是日程表)
        self.data.set_stat(f"tasks.{self.name}.next_run", time_str)
        self.logger.info(f"下次运行安排在: {time_str}")

    # ==========================================
    # 🏃 运行入口 (不要重写这个，重写 run_impl)
    # ==========================================
    def execute(self):
        """
        调度器调用的标准入口
        1. 检查是否真的要跑
        2. 执行逻辑
        3. 自动更新下次时间
        """
        self.logger.info(f"=== 任务启动: {self.name} ===")
        
        # 1. 更新 UI 状态
        self.data.set_runtime("current_task", self.name)
        
        # 2. 执行具体逻辑 (子类实现)
        try:
            success = self.run_impl()
        except Exception as e:
            self.logger.error(f"任务崩溃: {e}")
            success = False
        
        # 3. 完事后，安排下次时间
        # 如果任务失败了，是立即重试还是按原计划？这里暂定按原计划
        # ALAS 的做法是：如果失败，可能只 sleep 5分钟而不是 1小时
        if success:
            self.set_next_run() # 用 config 里的正常间隔
        else:
            self.set_next_run(seconds=300) # 失败后 5 分钟重试
            
        self.logger.info(f"=== 任务结束: {self.name} ===")

    def run_impl(self):
        """
        【子类请重写这个方法】
        真正的业务逻辑写在这里 (打怪、采集等)
        :return: True(成功) / False(失败)
        """
        raise NotImplementedError

    # ==========================================
    # 🛠️ 常用快捷指令 (Shortcut)
    # ==========================================
    def screenshot(self):
        """任务中截图"""
        # 调用 device 的截图功能，tag 是任务名
        pass # 实际调用 basic.py