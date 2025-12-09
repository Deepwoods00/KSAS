# tasks/daily/vip_chest.py
# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta, timezone
from tasks.base_task import BaseTask
from i18n.i18n import get_text

class VipChestTask(BaseTask):
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable",
            "default": False,
            "menu": "Daily"
        }
    ]

    @property
    def name(self):
        return "VipChestTask"

    @property
    def priority(self):
        return 20

    @property
    def default_interval(self):
        return 3600

    def run_impl(self):
        self.logger.info("开始执行 VIP 每日奖励领取...")

        # 1. Ensure Home
        self.device.ensure_home()
        time.sleep(0.8)
        
        # 2. 点击顶部 VIP 图标 (607, 78)
        self.logger.info("点击 VIP 入口 (607, 78)")
        self.device.click((607, 78))
        time.sleep(2.0) 

        # 3. 点击 (625, 280) 两次，间隔 0.4s
        target_pos_1 = (625, 280)
        self.logger.info(f"点击 {target_pos_1} x2")
        self.device.click(target_pos_1)
        time.sleep(0.4)
        self.device.click(target_pos_1)
        
        time.sleep(1.5)

        # 4. 点击 (614, 820) 两次，间隔 0.4s
        target_pos_2 = (614, 820)
        self.logger.info(f"点击 {target_pos_2} x2")
        self.device.click(target_pos_2)
        time.sleep(0.4)
        self.device.click(target_pos_2)

        time.sleep(1.5)

        # 5. 按一次 Back 返回主页
        self.logger.info("返回主页")
        self.device.press_back()
        time.sleep(1.0)
        
        # 6. 任务完成，定好明天的闹钟
        self._schedule_next_run()
        
        return True

    def _schedule_next_run(self):
        # 获取当前 UTC 时间
        now = datetime.now(timezone.utc)
        
        # 直接计算明天的日期：当前时间 + 1天
        tomorrow = now + timedelta(days=1)
        
        # 设置具体时间为 00:01:00
        target_time = tomorrow.replace(hour=0, minute=1, second=0, microsecond=0)

        # 计算秒数差
        wait_seconds = (target_time - now).total_seconds()
        
        self.logger.info(f"任务完成，下一次运行定于: {target_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        self.set_next_run(seconds=wait_seconds)