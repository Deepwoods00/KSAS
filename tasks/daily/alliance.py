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
            self.logger.info("Clicking Alliance Icon")
            self.device.click(self.IMG_ALLIANCE_ICON)
            self.device.sleep(2.0)
            return True
        else:
            self.logger.error("Alliance Icon not found")
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
        self.logger.info(">>> Starting Tech Donation")
        
        if not self.enter_alliance_view():
            return False

        # Click Tech
        if self.device.exists(self.IMG_TECH_ICON):
            self.logger.info("Clicking Tech Icon")
            self.device.click(self.IMG_TECH_ICON)
            self.device.sleep(1.5)
        else:
            self.logger.warning("Tech Icon not found")
            return False

        # Check Thumb/Donation available
        if self.device.exists(self.IMG_THUMB_ICON):
            self.logger.info("Found Recommended Tech (Thumb), clicking...")
            self.device.click(self.IMG_THUMB_ICON)
            self.device.sleep(1.0)
            
            # Long Press Donation Button
            self.logger.info("Long pressing donation button...")
            self.device.swipe((470, 1020), (470, 1020), duration=6.0)
            self.device.sleep(1.0)
            
            self.device.ensure_home()
            return True
        else:
            self.logger.info("No Recommended Tech found, skipping donation.")
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
        self.logger.info(">>> Starting Chest Collection")
        
        if not self.enter_alliance_view():
            return False

        # Click Chest
        if self.device.exists(self.IMG_CHEST_ICON):
            self.logger.info("Clicking Chest Icon")
            self.device.click(self.IMG_CHEST_ICON)
            self.device.sleep(1.5)
        else:
            self.logger.warning("Chest Icon not found")
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