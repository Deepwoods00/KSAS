# tasks/daily/alliance.py
# -*- coding: utf-8 -*-

from tasks.base_task import BaseTask
from airtest.core.api import Template
from i18n.i18n import get_text

class AllianceBaseTask(BaseTask):
    """
    Base class for Alliance tasks to share assets and navigation logic.
    """
    def __init__(self, device, data):
        super().__init__(device, data)
        # --- Assets ---
        self.IMG_ALLIANCE_ICON = Template(r"assets/images/home/alliance.png", threshold=0.9)
        self.IMG_TECH_ICON = Template(r"assets/images/alliance/tech.png", threshold=0.9)
        self.IMG_THUMB_ICON = Template(r"assets/images/alliance/thumb.png", threshold=0.9)
        self.IMG_CHEST_ICON = Template(r"assets/images/alliance/chest.png", threshold=0.9)
        
        # Navigation
        self.IMG_BTN_TOWN = Template(r"assets/images/home/btn_town.png", threshold=0.9)

    def enter_alliance_view(self):
        """
        Navigate to Alliance View
        """
        self.device.ensure_home()
        
        if self.device.exists(self.IMG_ALLIANCE_ICON):
            self.logger.info(get_text("log_click_alliance_icon"))
            self.device.click(self.IMG_ALLIANCE_ICON)
            self.device.sleep(2.0)
            return True
        else:
            self.logger.error(get_text("log_alliance_icon_not_found"))
            return False

class AllianceTechTask(AllianceBaseTask):
    # UI Configuration
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Tech Donation",
            "default": False,
            "menu": "Alliance"
        }
    ]

    @property
    def name(self):
        return "AllianceTechTask"

    @property
    def priority(self):
        return 90 # Low priority

    @property
    def default_interval(self):
        return 14400 # 4 hours

    def run_impl(self):
        self.logger.info(get_text("log_start_tech_donation"))
        
        if not self.enter_alliance_view():
            return False

        # Click Tech
        if self.device.exists(self.IMG_TECH_ICON):
            self.logger.info(get_text("log_click_tech_icon"))
            self.device.click(self.IMG_TECH_ICON)
            self.device.sleep(1.5)
        else:
            self.logger.warning(get_text("log_tech_icon_not_found"))
            return False

        # Check Thumb/Donation available
        if self.device.exists(self.IMG_THUMB_ICON):
            self.logger.info(get_text("log_found_recommended_tech"))
            self.device.click(self.IMG_THUMB_ICON)
            self.device.sleep(1.0)
            
            # Long Press Donation Button
            self.logger.info(get_text("log_long_press_donation"))
            self.device.swipe((470, 1020), (470, 1020), duration=6.0)
            self.device.sleep(1.0)
            
            self.device.ensure_home()
            return True
        else:
            self.logger.info(get_text("log_no_recommended_tech"))
            self.device.ensure_home()
            return True

class AllianceChestTask(AllianceBaseTask):
    # UI Configuration
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Chest Collection",
            "default": False,
            "menu": "Alliance"
        }
    ]

    @property
    def name(self):
        return "AllianceChestTask"

    @property
    def priority(self):
        return 90 # Low priority

    @property
    def default_interval(self):
        return 28800 # 8 hours

    def run_impl(self):
        self.logger.info(get_text("log_start_chest_collection"))
        
        if not self.enter_alliance_view():
            return False

        # Click Chest
        if self.device.exists(self.IMG_CHEST_ICON):
            self.logger.info(get_text("log_click_chest_icon"))
            self.device.click(self.IMG_CHEST_ICON)
            self.device.sleep(1.5)
        else:
            self.logger.warning(get_text("log_chest_icon_not_found"))
            return False

        # Sequence from MD
        # C_Pos1: Click (595, 395)
        self.device.click((595, 395))
        self.device.sleep(1.0)

        # C_Pos2: Click (572, 1187) x2
        self.device.click((572, 1187))
        self.device.sleep(0.4)
        self.device.click((572, 1187))
        self.device.sleep(1.0)

        # C_Pos3: Click (87, 385)
        self.device.click((87, 385))
        self.device.sleep(1.0)

        # C_Pos4: Click (321, 1193) x2
        self.device.click((321, 1193))
        self.device.sleep(0.4)
        self.device.click((321, 1193))
        self.device.sleep(1.0)

        # C_Pos5: Click (350, 140) x2 (Close/Back?)
        self.device.click((350, 140))
        self.device.sleep(0.4)
        self.device.click((350, 140))
        self.device.sleep(1.0)

        self.device.ensure_home()
        return True
    

class AllianceHelpTask(AllianceBaseTask):
    # UI 配置定义 (供 UI 自动生成简单的 Enable 选项，复杂配置我们在 task_widgets.py 里写)
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Alliance Help",
            "default": False,
            "menu": "Alliance"
        }
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        # 定义帮助图标的图片模板
        # 注意：使用文件列表中存在的 alli_help.png
        self.IMG_ALLI_HELP = Template(r"assets/images/alliance/alliance_help.png", threshold=0.9)

    @property
    def name(self):
        return "AllianceHelpTask"

    @property
    def priority(self):
        # 优先级设置得高一点，因为点帮助是举手之劳，应该尽快完成
        return 20 

    @property
    def default_interval(self):
        # 默认 10 分钟 (600秒)
        return 600

    def run_impl(self):
        self.logger.info(get_text("log_alliance_help_start", "检查联盟帮助"))
        
        # 1. Ensure Home (确保在主页)
        self.device.ensure_home()
        self.device.sleep(1.0) # 稍微等一下主页加载

        # 2. 检测并点击
        if self.device.exists(self.IMG_ALLI_HELP):
            self.logger.info(get_text("log_alliance_help_found", "发现帮助请求，点击中..."))
            self.device.click(self.IMG_ALLI_HELP)
            self.device.sleep(0.5)
            self.device.ensure_home()
        else:
            self.logger.info(get_text("log_alliance_help_not_found", "当前没有帮助请求"))

        # 无论点没点，都算任务成功
        return True