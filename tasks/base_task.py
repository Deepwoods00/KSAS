# tasks/base_task.py
# -*- coding: utf-8 -*-

import os
import logging
from airtest.core.api import Template
from datetime import datetime, timedelta

class BaseTask:
    """
    所有任务的基类 (ALAS 风格)
    
    核心属性：
    1. name: 任务名 (用于在 JSON 里查找配置)
    2. priority: 优先级 (数字越大越重要，或者越小越重要，这里我们定：数字越小优先级越高 1 > 10)
    3. default_interval: 默认间隔秒数 (如果 config 没填就用这个)
    """
    DIANA_COST_TABLE = {
        1: (23, 9),
        2: (22, 9),
        3: (22, 9),
        4: (21, 9),
        5: (20, 8)
    }

    # 默认消耗 (没有戴安娜时)
    DEFAULT_COST = (25, 10)



    def __init__(self, device, data):
        """
        :param device: basic.py 的 DeviceOperator
        :param data: datastore.py 的 InstanceDataStore
        """
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"{self.data.instance_id}.Task.{self.name}")

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

    def calculate_cost(self, mode="rally"):
        """
        计算本次出征的体力消耗
        :param mode: 'rally' (集结) 或 'beast' (打野)
        :return: int (消耗值)
        """
        # 1. 先看戴安娜在不在
        if self.find_diana():
            # 2. 如果在，去读配置里的技能等级
            # 我们把这个配置放在 general 里，因为它是账号属性
            skill_level = self.data.get_cfg("modules.general.diana_level", 1)
            
            # 查表
            costs = self.DIANA_COST_TABLE.get(skill_level, self.DEFAULT_COST)
            
            cost = costs[0] if mode == "rally" else costs[1]
            self.logger.info(f"触发戴安娜减耗 (Lv.{skill_level}): 本次消耗 {cost}")
            return cost
        
        else:
            # 3. 不在，用默认值
            cost = self.DEFAULT_COST[0] if mode == "rally" else self.DEFAULT_COST[1]
            self.logger.info(f"常规消耗: {cost}")
            return cost


    # ==========================================
    # 📊 游戏信息读取 (Game Info)
    # ==========================================

    def find_diana(self):
        """
        在出征界面寻找 Diana 的头像
        """
        # 记得把 Diana 的头像截图放在 assets/images/heroes/diana.png
        # 建议截那个圆圆的头像，特征明显一点
        img_diana = Template(r"assets/images/heroes/diana.png", threshold=0.9)
        
        if self.device.exists(img_diana):
            self.logger.info("检测到队伍包含 Diana")
            return True
        else:
            self.logger.debug("队伍中未检测到 Diana")
            return False











    """
    def get_current_stamina(self):
        '''
        读取当前体力值
        流程: 确保主页 -> 点头像 -> 点加号 -> OCR -> Back x2
        :return: int (当前体力)
        '''
        from airtest.core.api import Template

        # 1. 确保在主页
        if not self.device.ensure_home():
            self.logger.error("无法回到主页，放弃读取体力")
            return 0
            
        # 2. 点击头像 (8, 8, 80, 80)
        # Airtest 的 touch 支持绝对坐标 (x, y)
        # 我们取中心点 (44, 44)
        self.logger.info("点击头像进入 Profile")
        self.device.click((44, 44))
        self.device.sleep(2) # 等待动画
        
        # 3. 点击加号进入体力页
        # 假设加号图片是 assets/images/profile_plus.png
        img_plus = Template(r"assets/images/profile_plus.png")
        if not self.device.exists(img_plus):
            self.logger.error("未找到体力加号按钮")
            self.device.press_back() # 尝试退回
            return 0
            
        self.logger.info("点击加号查看体力")
        self.device.click(img_plus)
        self.device.sleep(1.5)
        
        # 4. OCR 识别
        # 区域: (350, 270, 480, 300)
        area = (350, 270, 480, 300) 
        text = self.device.get_text(area)
        self.logger.debug(f"OCR Stamina Raw: {text}")
        
        # 5. 解析 "100/200" 格式
        if "/" in text:
            current_str = text.split("/")[0]
        else:
            current_str = text
        val = self.device.parse_number(current_str)
        
        # 6. 更新到 DataStore
        self.data.set_stat("stamina", val)
        self.logger.info(f"当前体力: {val}")
        
        # 7. 返回主页 (Back x2)
        self.logger.info("返回主页")
        self.device.press_back()
        self.device.sleep(1)
        self.device.press_back()
        self.device.sleep(1)
        
        return val
    """