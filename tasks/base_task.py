# tasks/base_task.py
# -*- coding: utf-8 -*-

import os
import logging
import time
from airtest.core.api import Template
from datetime import datetime, timedelta
from i18n.i18n import get_text
from game.sidebar import Sidebar

class BaseTask:
    """
    所有任务的基类 (ALAS 风格)
    """
    
    def __init__(self, device, data):
        self.device = device
        self.data = data
        self.logger = logging.getLogger(f"{self.data.instance_id}.Task.{self.name}")
        self.sidebar = Sidebar(device, data)

    # ==========================================
    # ⚙️ 属性配置
    # ==========================================
    @property
    def name(self):
        return "BaseTask"

    @property
    def priority(self):
        return 50

    @property
    def default_interval(self):
        return 3600

    # ==========================================
    # ⏱️ 调度逻辑
    # ==========================================
    @property
    def enabled(self):
        return self.data.get_cfg(f"modules.{self.name.lower()}.enable", False)

    @property
    def next_run(self):
        time_str = self.data.get_stat(f"tasks.{self.name}.next_run", "1970-01-01 00:00:00")
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.min 

    def set_next_run(self, seconds=None, timestamp=None):
        if timestamp:
            future_time = datetime.fromtimestamp(timestamp)
        else:
            if seconds is None:
                seconds = self.data.get_cfg(f"modules.{self.name.lower()}.interval", self.default_interval)
            future_time = datetime.now() + timedelta(seconds=int(seconds))
            
        time_str = future_time.strftime("%Y-%m-%d %H:%M:%S")
        
        self.data.set_stat(f"tasks.{self.name}.next_run", time_str)
        self.logger.info(get_text("log_next_run_scheduled", time_str))

    # ==========================================
    # 🏃 运行入口
    # ==========================================
    def execute(self):
        self.logger.info(get_text("log_task_started", self.name))
        self.data.set_runtime("current_task", self.name)
        
        try:
            success = self.run_impl()
        except Exception as e:
            self.logger.error(get_text("log_task_crashed", e))
            success = False
        
        if success:
            # 如果任务执行成功，但被禁用了（例如 WolfTask 次数耗尽），就不再安排下次运行
            if self.enabled:
                self.set_next_run()
            else:
                self.logger.info(f"任务 {self.name} 已禁用，停止调度")
        else:
            self.set_next_run(seconds=300)
            
        self.logger.info(get_text("log_task_finished", self.name))

    def run_impl(self):
        raise NotImplementedError

    # ==========================================
    # 🎮 通用游戏操作 (核心逻辑)
    # ==========================================

    def select_search_level(self, target_level):
        """
        通用的等级调整逻辑 (侦察 -> 归零 -> 调整 -> 核实)
        :param target_level: int, 目标等级 (1-29)
        """
        # ==========================================
        # 🛑 请务必修改这些坐标！(720x1280分辨率下)
        # ==========================================
        SLIDER_LEFT = (120, 1053) # 滑动条最左端 (能点到1级的位置)
        BTN_MINUS = (69, 1053)    # 减号按钮中心
        BTN_PLUS = (487, 1053)    # 加号按钮中心
        BTN_SEARCH = (360, 1214) # 底部巨大的搜索按钮
        
        # 图片路径模板
        IMG_LEVEL_TPL = r"assets/images/map_level/{}.png"
        IMG_MINUS_GRAY = Template(r"assets/images/map_level/grey_minus.png", threshold=0.95)

        self.logger.info(get_text("log_adjust_level_start", target_level))

        # --- 1. 侦察阶段 (Pre-Check) ---
        # 如果当前屏幕上已经显示了目标等级，直接去搜索，省时省力
        target_img_path = IMG_LEVEL_TPL.format(target_level)
        
        # 检查图片是否存在 (利用 basic.py 的 _exists_internal)
        if os.path.exists(target_img_path):
            target_tpl = Template(target_img_path, threshold=0.9)
            if self.device.exists(target_tpl):
                self.logger.info(get_text("log_level_already_match", target_level))
                self.device.click(BTN_SEARCH)
                return True
        else:
            self.logger.warning(get_text("log_level_img_missing", target_img_path))

        # --- 2. 归零阶段 (Reset to 1) ---
        self.logger.info(get_text("log_level_resetting"))
        
        # A. 猛击滑动条左侧 (快速降级)
        self.device.click(SLIDER_LEFT)
        self.device.sleep(0.5) # 等动画

        # B. 灰色检测与补刀 (确保降到 1)
        is_reset_success = False
        for _ in range(15): # 最多补点15次，防死循环
            if self.device.exists(IMG_MINUS_GRAY):
                # self.logger.debug("减号已变灰，归零成功")
                is_reset_success = True
                break
            else:
                # 还没灰，说明还没到1级，点减号补刀
                self.device.click(BTN_MINUS, times=1)
                # time.sleep(0.1) # click 内部已有 sleep，这里不用加太久

        if not is_reset_success:
            self.logger.warning(get_text("log_reset_warning"))

        # --- 3. 调整阶段 (Adjust) ---
        # 现在默认是 Lv.1
        clicks_needed = target_level - 1
        
        if clicks_needed > 0:
            self.logger.info(get_text("log_level_upgrading", clicks_needed))
            # 为了速度，我们可以直接调用 adb 连点，绕过 device.click 的 sleep
            for _ in range(clicks_needed):
                self.device.adb.touch(BTN_PLUS)
                time.sleep(0.1) # 80ms 间隔，极速连点
            self.device.sleep(0.8) # 等数字跳完

        # --- 4. 核实阶段 (Verify) ---
        # 再看一眼是不是我们要的等级
        if os.path.exists(target_img_path):
            if not self.device.exists(target_tpl):
                self.logger.error(get_text("log_level_adjust_failed", target_level))
                # 失败策略：是重试还是硬着头皮搜？
                # 这里选择硬着头皮搜，万一只是图片识别不到呢
            else:
                self.logger.info(get_text("log_level_verify_success", target_level))

        # --- 5. 搜索 ---
        self.logger.info(get_text("log_click_search"))
        self.device.click(BTN_SEARCH)
        self.device.sleep(1.5) # 等待界面切换
        return True

    # ==========================================
    # 📊 辅助功能
    # ==========================================
