import time
from datetime import datetime, timezone, timedelta
from airtest.core.api import Template
from tasks.base_task import BaseTask
from i18n.i18n import get_text

class RecruitAdvTask(BaseTask):
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
        self.IMG_BOX = Template(r"assets/images/sidebar/silver_box.png", threshold=0.9)
        # 注意：这里开启 rgb=True, threshold=0.94 以区分灰色和亮色的 GO
        self.IMG_GO = Template(r"assets/images/sidebar/go.png", threshold=0.94, rgb=True)
        
        # 招募按钮坐标 (根据需求硬编码)
        self.POS_RECRUIT_BTN = (101, 841)

    @property
    def name(self):
        return "RecruitAdvTask"

    @property
    def priority(self):
        return 11 # 优先级中等

    @property
    def default_interval(self):
        return 310 # 默认间隔并不重要，因为我们会手动 set_next_run

    def run_impl(self):
        self.logger.info(get_text("log_recruit_start"))
        
        # === 1. 日期检查与重置 (Date Check) ===
        if self._check_new_day():
            self.logger.info("New UTC day detected. Resetting counters.")
            self._reset_counters()

        # === 2. 上限检查 (Limit Check) ===
        daily_count = self.data.get_stat("tasks.RecruitAdvTask.daily_count", 0)
        if daily_count >= 5:
            self.logger.info(get_text("log_recruit_daily_limit", daily_count))
            self._schedule_tomorrow()
            return True

        # === 3. 导航 (Nav) ===
        if not self.sidebar.switch_to_affairs_page():
            self.logger.warning("Failed to navigate to Affairs page.")
            self._handle_failure()
            return False

        # === 4. 扫描循环 (Scan Loop) ===
        # 策略：先看当前屏，没找到则上滑看下面，共试2次
        found_box_pos = None
        
        for i in range(2):
            self.logger.info(f"Scanning for silver box ({i+1}/2)...")
            
            # 4.1 寻找锚点 (Silver Box)
            # find_in_anchor_row 内部包含了截图，所以我们先用 exists 快速判断有没有箱子
            # 但我们需要箱子的坐标传给 find_in_anchor_row 吗？
            # 不，sidebar.find_in_anchor_row 内部会自己找 anchor_tpl。
            # 为了效率，我们直接调用 find_in_anchor_row
            
            # 在同一行寻找 GO 图标
            # 参数: 锚点, 目标, X范围(默认), Y外扩(默认)
            # 注意：find_in_anchor_row 返回的是 GO 的坐标，不是 Box 的坐标
            # 但我们需要点击 Box。
            # 所以我们需要先手动找 Box。
            
            box_pos = self.device.exists(self.IMG_BOX)
            if box_pos:
                # 找到了盒子，检查同行有没有 GO
                go_pos = self.sidebar.find_in_anchor_row(self.IMG_BOX, self.IMG_GO)
                
                if go_pos:
                    # === 分支 A: 找到了 GO (有免费次数) ===
                    self.logger.info(get_text("log_recruit_found_free"))
                    self._perform_recruitment(box_pos)
                    return True
                else:
                    self.logger.info("Box found but NO 'GO' button (Cooldown or Used).")
                    # 这里不算失败，可能是CD没好，继续找或者结束
                    # 如果当前屏找到了盒子但没GO，且下面没有盒子了，那就是CD没好
                    # 但为了保险，我们还是继续滑一下看看有没有另一个盒子
            
            # 没找到盒子，或者找到了盒子但没GO -> 滑动
            if i < 1:
                self.sidebar.scroll_up()

        # === 5. 循环结束仍未执行 (分支 B: 无免费次数) ===
        self.logger.warning("No free recruitment available.")
        self._handle_failure()
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
        self.logger.info("Clicking recruit button...")
        self.device.click(self.POS_RECRUIT_BTN)
        time.sleep(1.5)
        
        # 3. 数据更新
        current_daily = self.data.get_stat("tasks.RecruitAdvTask.daily_count", 0) + 1
        self.data.set_stat("tasks.RecruitAdvTask.daily_count", current_daily)
        self.data.set_stat("tasks.RecruitAdvTask.retry_count", 0) # 成功则重置重试计数
        self.logger.info(get_text("log_recruit_success", current_daily))
        
        # 4. 回主页
        self.device.ensure_home()
        
        # 5. 设置下次运行时间
        if current_daily >= 5:
            self._schedule_tomorrow()
        else:
            # 等待CD: 5分10秒 = 310秒
            self.logger.info("Waiting for cooldown (5m 10s)...")
            self.set_next_run(seconds=310)

    def _handle_failure(self):
        """处理失败/未找到的情况 (分支 B)"""
        retry = self.data.get_stat("tasks.RecruitAdvTask.retry_count", 0)
        
        if retry >= 2:
            # B1: 连续失败 2 次 -> 明天再来
            self.logger.warning(f"Failed {retry+1} times. Giving up for today.")
            self._reset_counters(reset_daily=False, reset_retry=True)
            self._schedule_tomorrow()
        else:
            # B2: 还没到限制 -> 稍后重试
            new_retry = retry + 1
            self.data.set_stat("tasks.RecruitAdvTask.retry_count", new_retry)
            self.logger.warning(f"Retrying later ({new_retry}/2). Wait 5m 30s.")
            self.set_next_run(seconds=330) # 5分30秒
            
        self.sidebar.collapse()

    def _schedule_tomorrow(self):
        """设置下次运行时间为 UTC 明日 00:01"""
        now_utc = datetime.now(timezone.utc)
        tomorrow = now_utc.replace(hour=0, minute=1, second=0, microsecond=0) + timedelta(days=1)
        
        # 计算秒数差
        wait_seconds = (tomorrow - now_utc).total_seconds()
        
        self.logger.info(f"Task finished for today. Next run: {tomorrow.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.set_next_run(seconds=wait_seconds)

    def _check_new_day(self):
        """检查是否跨天 (UTC)"""
        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_date = self.data.get_stat("tasks.RecruitAdvTask.last_run_date", "")
        
        if now_date != last_date:
            self.data.set_stat("tasks.RecruitAdvTask.last_run_date", now_date)
            return True
        return False

    def _reset_counters(self, reset_daily=True, reset_retry=True):
        if reset_daily:
            self.data.set_stat("tasks.RecruitAdvTask.daily_count", 0)
        if reset_retry:
            self.data.set_stat("tasks.RecruitAdvTask.retry_count", 0)