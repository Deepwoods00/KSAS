# tasks/daily/recruit_epic.py
# -*- coding: utf-8 -*-
import time
from airtest.core.api import Template
from tasks.base_task import BaseTask
from i18n.i18n import get_text

class RecruitEpicTask(BaseTask):
    # UI 配置
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable",
            "default": False,
            "menu": "Daily"
        }
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        # 资源定义
        # 锚点: 金箱子
        self.IMG_BOX = Template(r"assets/images/sidebar/gold_box.png", threshold=0.9)
        # 目标: GO 图标 (开启 RGB 校验以区分灰色状态)
        self.IMG_GO = Template(r"assets/images/sidebar/go.png", threshold=0.94, rgb=True)
        
        # 招募按钮坐标 (史诗招募)
        self.POS_RECRUIT_BTN = (139, 1199)

    @property
    def name(self):
        return "RecruitEpicTask"

    @property
    def priority(self):
        return 66 # 略高于高级招募

    @property
    def default_interval(self):
        return 1200 # 默认 20分钟 (找不到时的CD)

    def run_impl(self):
        self.logger.info(get_text("log_recruit_epic_start"))
        
        # 1. 导航
        if not self.sidebar.switch_to_affairs_page():
            self.logger.warning("Failed to navigate to Affairs page.")
            self._handle_wait_short()
            return False

        # 2. 扫描循环 (2次)
        for i in range(2):
            self.logger.info(f"Scanning for gold box ({i+1}/2)...")
            
            # 2.1 寻找锚点 (Gold Box)
            box_pos = self.device.exists(self.IMG_BOX)
            
            if box_pos:
                # 2.2 找到了盒子，检查同行 GO
                go_pos = self.sidebar.find_in_anchor_row(self.IMG_BOX, self.IMG_GO)
                
                if go_pos:
                    # === 分支 A: 找到了 GO (有免费次数) ===
                    self.logger.info(get_text("log_recruit_found_free"))
                    self._perform_recruitment(box_pos)
                    return True
                else:
                    self.logger.info("Gold box found but NO 'GO' button (Cooldown).")
                    # 找到了盒子但没GO，说明CD没好，不用继续找了
                    # 直接跳出循环去设置短CD
                    break 
            
            # 没找到盒子，或者盒子不在当前屏 -> 滑动
            if i < 1:
                self.sidebar.scroll_up()

        # === 3. 没找到或CD中 (分支 B) ===
        self.logger.info(get_text("log_recruit_epic_cooldown"))
        self._handle_wait_short()
        return True

    # -------------------------------------------------------------------------
    # 逻辑辅助函数
    # -------------------------------------------------------------------------

    def _perform_recruitment(self, box_pos):
        """执行招募动作"""
        # 1. 点击盒子
        self.device.click(box_pos)
        time.sleep(1.0)
        
        # 2. 点击招募按钮 (固定坐标)
        self.logger.info("Clicking epic recruit button...")
        self.device.click(self.POS_RECRUIT_BTN)
        time.sleep(1.5)
        
        self.logger.info(get_text("log_recruit_epic_success"))
        
        # 3. 回主页
        self.device.ensure_home()
        
        # 4. 设置下次运行: 48小时
        wait_seconds = 48 * 3600
        self.logger.info(f"Epic recruit done. Waiting 48 hours.")
        self.set_next_run(seconds=wait_seconds)

    def _handle_wait_short(self):
        """处理等待逻辑: 20分钟"""
        wait_seconds = 20 * 60
        self.logger.info(f"Not available. Retry in 20 mins.")
        
        self.sidebar.collapse()
        self.set_next_run(seconds=wait_seconds)