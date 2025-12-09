# tasks/daily/intel.py
# -*- coding: utf-8 -*-

import time
import cv2
import numpy as np
from datetime import datetime, timedelta, timezone
from airtest.core.api import Template
from tasks.combat.combat_task import CombatTask
from tasks.daily.stamina_control import StaminaControlTask
from i18n.i18n import get_text

class IntelTask(CombatTask):
    # UI Configuration
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable_intel",
            "default": False,
            "menu": "Daily"
        },
        {
            "key": "desc",
            "type": "label",
            "label": "cfg_intel_desc"
        }
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        # --- Assets ---
        # Intel Entry
        self.IMG_INTEL_ICON = Template(r"assets/images/home/intel.png", threshold=0.9)
        
        # Task Icons (Shape Only - Using White/High Contrast version)
        self.ICON_THRESHOLD = 0.85 # Slightly lower for shape matching across colors
        
        self.ICONS = {
            "Tavern": Template(r"assets/images/intel/intel_tavern_white.png", threshold=self.ICON_THRESHOLD, rgb=False),
            "Tent": Template(r"assets/images/intel/intel_tent_white.png", threshold=self.ICON_THRESHOLD, rgb=False),
            "Beast": Template(r"assets/images/intel/intel_beast_white.png", threshold=self.ICON_THRESHOLD, rgb=False),
            "Event": Template(r"assets/images/intel/intel_event.png", threshold=self.ICON_THRESHOLD, rgb=False),
        }

        # Task Execution
        self.IMG_TAVERN_CHECK = Template(r"assets/images/intel/tavern_check.png", threshold=0.8)
        
        # Buttons
        self.IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.85, rgb=True)
        self.IMG_BTN_GREEN = Template(r"assets/images/btn/btn_green.png", threshold=0.85, rgb=True)
        self.IMG_BTN_ORANGE = Template(r"assets/images/btn/btn_orange.png", threshold=0.85, rgb=True)
        self.IMG_EQUAL = Template(r"assets/images/combat/equal.png", threshold=0.9)
        
        # Navigation
        self.IMG_BTN_TOWN = Template(r"assets/images/home/btn_town.png", threshold=0.9)
        self.IMG_BTN_GO_MAP = Template(r"assets/images/home/btn_go_map.png", threshold=0.9)

        # Stamina/Red Dot Checks
        # These need to be defined or we use pixel checks. 
        # For now, assuming pixel checks are done via device.get_pixel or similar if coordinates known,
        # or we use small templates if provided. 
        # The MD mentions "Check Red Pixel". We'll implement helper for that.

    @property
    def name(self):
        return "IntelTask"

    @property
    def priority(self):
        return 25

    @property
    def default_interval(self):
        # 00:02, 08:02, 16:02 UTC
        now = datetime.now(timezone.utc)
        targets = [0, 8, 16]
        next_run = None
        
        for h in targets:
            target_time = now.replace(hour=h, minute=2, second=0, microsecond=0)
            if target_time > now:
                next_run = target_time
                break
                
        if not next_run:
            # Tomorrow 00:02
            next_run = now.replace(hour=0, minute=2, second=0, microsecond=0) + timedelta(days=1)
            
        # Return seconds until next run
        return (next_run - now).total_seconds()

    def run_impl(self):
        self.logger.info(get_text("log_intel_start"))

        # --- 0. Pre-checks ---
        if not self._check_stamina_and_queue():
            return False

        # --- 2. Batch Scan & Execute Loop ---
        while True:
            # --- 1. Navigate to Intel ---
            if not self._navigate_to_intel():
                return False

            # 2.1 Batch Scan
            task_list = self._scan_all_targets()
            
            if not task_list:
                self.logger.info(get_text("log_intel_finished", get_text("log_intel_no_more_targets")))
                break
                
            self.logger.info(get_text("log_intel_found_tasks", len(task_list), [t[0] for t in task_list]))
            
            # 2.2 Loop Execution
            for task_type, pos in task_list:
                self.logger.info(get_text("log_intel_executing", task_type, pos))
                
                # Click the task icon
                self.device.click(pos)
                self.device.sleep(1.0)
                
                # Dispatch
                result = False
                if task_type == "Tavern":
                    result = self._handle_tavern()
                elif task_type == "Tent":
                    result = self._handle_tent()
                elif task_type == "Beast":
                    result = self._handle_beast()
                elif task_type == "Event":
                    result = self._handle_event()
                
                if result == "RESCAN":
                    self.logger.info("Rescanning targets...")
                    break

                if not result:
                    # If a task failed (e.g. stamina low, error), we might need to stop or return
                    # Based on MD, most failures lead to GoHomeError -> return False
                    # But some might just be skip?
                    # For now, if handle returns False, we assume it handled the exit/logging
                    return False

                if not self._navigate_to_intel():
                    return False
                self.device.sleep(1.0) # Wait for view to settle

        # --- 3. Finish & Return Home ---
        self.logger.info(get_text("log_intel_finished", get_text("log_intel_finished_all")))
        self.device.ensure_home()
        return True

    def _check_stamina_and_queue(self):
        self.update_stamina()
        # 1. Check Stamina
        current_stamina = self.data.get_stat("stamina", 120)
        if current_stamina < 10:
            delay_min = (10 - current_stamina) * 5
            self.logger.info(get_text("log_intel_stamina_low", current_stamina, 10))
            self.set_next_run(seconds=delay_min * 60)
            return False
            
        # 2. Check Queue
        idle_queues = self.sidebar.get_idle_march_queues()
        if idle_queues == 0:
            self.logger.info(get_text("log_sidebar_idle_count", 0))
            self.set_next_run(seconds=600)
            return False
            
        return True

    def _navigate_to_intel(self):
        """
        Navigate to Intel page and reset view.
        This is used both for initial entry and for returning after a task.
        It ensures the view state is consistent (reset) for coordinate reuse.
        """
        # 1. Check if we are already in Wild (Intel icon visible)
        # If we just finished a task, we are likely in Wild.
        if self.device.exists(self.IMG_INTEL_ICON):
            self.logger.info(get_text("log_intel_already_wild"))
            self.device.click(self.IMG_INTEL_ICON)
            self.device.sleep(1.5)
            # Reset View (Critical for coordinate consistency)
            self._click_reset_pixel()
            return True

        # 2. If not, ensure we are at Home (or Wild) to start fresh
        # This handles cases where we might be in a sub-menu or weird state
        self.device.ensure_home()
        self.device.sleep(0.5)

        # 3. Check if in Wild (Intel icon is only visible in Wild/Map view)
        if not self.device.exists(self.IMG_BTN_TOWN):
            if self.device.exists(self.IMG_BTN_GO_MAP):
                self.logger.info(get_text("log_intel_switch_map"))
                self.device.click(self.IMG_BTN_GO_MAP)
                self.device.sleep(1.0)
            else:
                # If neither Town button nor Go Map button is visible, we might be lost
                pass

        # 4. Click Intel Icon
        if self.device.exists(self.IMG_INTEL_ICON):
            self.logger.info(get_text("log_click_search"))
            self.device.click(self.IMG_INTEL_ICON)
            self.device.sleep(1.5)
            
            # 5. Reset View (Critical for coordinate consistency)
            self._click_reset_pixel()
        else:
            self.logger.error(get_text("log_intel_enter_fail"))
            return False

        return True

    def _click_reset_pixel(self):
        # Click specific coordinate twice to reset view
        # (360, 1120) from previous code
        self.device.click((360, 1120))
        self.device.sleep(0.5)
        self.device.click((360, 1120))
        self.device.sleep(1.0)

    def _scan_all_targets(self):
        """
        Snapshot once, then match all 3 types.
        Returns list of (Type, Pos)
        """
        try:
            # 1. Snapshot (Using DeviceOperator wrapper)
            # This saves to file and returns path
            screen_path = self.device.snapshot()
            if not screen_path:
                self.logger.error(get_text("log_intel_snapshot_fail"))
                return []
                
            # 2. Read Image
            screen = cv2.imread(screen_path)
            if screen is None:
                self.logger.error(get_text("log_intel_read_fail", screen_path))
                return []
                
            targets = []
            
            # 3. Match All In
            for task_type, template in self.ICONS.items():
                # match_all_in returns list of results (dicts or coordinates depending on version, usually dicts with 'result')
                results = template.match_all_in(screen)
                
                if results:
                    for res in results:
                        # Airtest match_all_in returns list of dicts: {'result': (x,y), 'rectangle': ..., 'confidence': ...}
                        if isinstance(res, dict) and 'result' in res:
                            pos = res['result']
                            targets.append((task_type, pos))
                        elif isinstance(res, (tuple, list)):
                            # Just in case it returns raw coordinates
                            targets.append((task_type, res))
            
            return targets
            
        except Exception as e:
            self.logger.error(get_text("log_intel_scan_fail", e))
            return []

    def _post_task_sequence(self):
        # Ensure we are back at Intel (should be handled by task return, but double check)
        # Then click reset pixel
        self._click_reset_pixel()

    def _handle_tavern(self):
        self.logger.info(get_text("log_intel_executing", "Tavern", ""))
        # 1. Click Blue (Start)
        if not self.device.exists(self.IMG_BTN_BLUE):
            self.logger.info(get_text("log_intel_tavern_blue_missing"))
            return True # Treat as success to continue loop
            
        if not self.device.click(self.IMG_BTN_BLUE): return False
        self.device.sleep(1.0)
        
        # 2. Check Stamina
        req_stamina = 10
        stamina_check = self.check_stamina_sufficient(req_stamina)
        
        if stamina_check == "RESTART":
            return "RESCAN"
            
        if isinstance(stamina_check, int) and not isinstance(stamina_check, bool): 
            self.logger.info(get_text("log_intel_tavern_stamina_low"))
            
            # [新增] 尝试自救
            if self._try_rescue_stamina():
                self.logger.info("Stamina rescued. Restarting scan.")
                return "RESCAN" # 返回 RESCAN，让主循环重新进入地图
            
            # [旧逻辑] 自救失败，计算等待时间
            delay_min = max(1, stamina_check * 5)
            self.set_next_run(seconds=delay_min * 60)
            self.device.ensure_home()
            return False

        # 3. Click blue (Using Region)
        # Region: (365, 628)
        self.device.click((365, 628))
        self.device.sleep(1.0)

        # 4. click green
        if not self.device.click((470, 1200)): return False
        
        # 5. Scan for Check
        self.logger.info(get_text("log_intel_tavern_scan"))
        start_time = time.time()
        found = False
        while time.time() - start_time < 60:
            if self.device.exists(self.IMG_TAVERN_CHECK):
                found = True
                break
            self.device.sleep(1.3)
            
        if found:
            self.device.press_back()
            self.device.sleep(1.0)
            self._update_stats(cost=10)
            return True
        else:
            self.logger.error(get_text("log_intel_tavern_timeout"))
            self.device.ensure_home()
            return False

    def _handle_tent(self):
        self.logger.info(get_text("log_intel_executing", "Tent", ""))
        # 1. Click Blue
        if not self.device.exists(self.IMG_BTN_BLUE):
            self.logger.info(get_text("log_intel_tent_blue_missing"))
            return True # Treat as success to continue loop

        if not self.device.click(self.IMG_BTN_BLUE): return False
        self.device.sleep(1.0)
        
        # 2. Check Stamina
        req_stamina = 12
        stamina_check = self.check_stamina_sufficient(req_stamina)
        
        if stamina_check == "RESTART":
            return "RESCAN"
            
        if isinstance(stamina_check, int) and not isinstance(stamina_check, bool): 
            self.logger.info(get_text("log_intel_tent_stamina_low"))
            
            # [新增] 尝试自救
            if self._try_rescue_stamina():
                return "RESCAN"
            
            # [旧逻辑]
            delay_min = max(1, stamina_check * 5)
            self.set_next_run(seconds=delay_min * 60)
            self.device.ensure_home()
            return False
            
        # 3. Click Green (Using Region)
        # Region: (365, 628)
        self.device.click((365, 628))
        self.device.sleep(1.0)
        
        self._update_stats(cost=12)
        return True

    def _handle_beast(self):
        self.logger.info(get_text("log_intel_executing", "Beast", ""))
        
        # 1. Check Queue
        idle_queues = self.data.get_stat("sidebar.idle_queues", 0)
        if idle_queues == 0:
            # Double check logic
            self.logger.info("Cached idle queues is 0. Double checking...")
            self.device.ensure_home()
            idle_queues = self.sidebar.get_idle_march_queues()
            
            if idle_queues == 0:
                self.logger.info(get_text("log_intel_beast_no_queue"))
                self.set_next_run(seconds=300)
                # self.device.ensure_home() # Already at home
                return False
            else:
                self.logger.info(f"Found {idle_queues} idle queues. Restarting scan.")
                return "RESCAN"

        # 2. Click Blue
        if not self.device.exists(self.IMG_BTN_BLUE):
            self.logger.info(get_text("log_intel_beast_blue_missing"))
            return True # Treat as success to continue loop

        if not self.device.click(self.IMG_BTN_BLUE): return False
        self.device.sleep(1.0)
        
        # 3. Click Orange
        if not self.device.click(self.IMG_BTN_ORANGE): return False
        self.device.sleep(1.0)
        
        # 4. Check Stamina
        req_stamina = 10 # As per instruction
        stamina_check = self.check_stamina_sufficient(req_stamina)
        
        if stamina_check == "RESTART":
            return "RESCAN"
            
        if isinstance(stamina_check, int) and not isinstance(stamina_check, bool):
            self.logger.info(get_text("log_intel_beast_stamina_low"))
            
            # [新增] 尝试自救
            if self._try_rescue_stamina():
                return "RESCAN"
            
            # [旧逻辑]
            delay_min = max(1, stamina_check * 5)
            self.set_next_run(seconds=delay_min * 60)
            self.device.ensure_home()
            return False
            
        # 5. Calculate Cost (High Stamina)
        # Determine cost before action
        cost = self.calculate_cost(mode="wild")
        
        # 6. Click Equal
        if not self.device.click(self.IMG_EQUAL): return False
        self.device.sleep(1.0)
        
        # 7. Click Blue2 (March) (Using Region)
        # Region: (546, 1213)
        self.device.click((546, 1213))
        self.device.sleep(2.0)
        
        # 8. Check Home (Success)
        if self.device.exists(self.IMG_INTEL_ICON) or self.device.exists(self.IMG_BTN_TOWN):
            # Success
            self._update_stats(cost=cost, queue=1)
            
            # Check Queue After
            if self.data.get_stat("sidebar.idle_queues", 0) == 0:
                self.logger.info(get_text("log_intel_beast_queue_full"))
                self.set_next_run(seconds=300)
                self.device.ensure_home()
                return False
                
            return True
        else:
            self.logger.error(get_text("log_intel_beast_home_fail"))
            self.device.ensure_home()
            return False
        

    def _handle_event(self):
        """
        处理 Event 任务 (逻辑与 Beast 一致)
        """
        self.logger.info(get_text("log_intel_executing", "Event", ""))
        
        # 1. Check Queue (检查队列)
        idle_queues = self.data.get_stat("sidebar.idle_queues", 0)
        if idle_queues == 0:
            # Double check logic
            self.logger.info("Cached idle queues is 0. Double checking...")
            self.device.ensure_home()
            idle_queues = self.sidebar.get_idle_march_queues()
            
            if idle_queues == 0:
                # 复用 Beast 的日志 key，或者你可以去 zh.yaml 加一个新的
                self.logger.info(get_text("log_intel_beast_no_queue")) 
                self.set_next_run(seconds=300)
                return False
            else:
                self.logger.info(f"Found {idle_queues} idle queues. Restarting scan.")
                return "RESCAN"

        # 2. Click Blue (点击蓝色按钮 - 前往)
        if not self.device.exists(self.IMG_BTN_BLUE):
            self.logger.info("Event blue button missing, skipping.")
            return True # Treat as success to continue loop

        if not self.device.click(self.IMG_BTN_BLUE): return False
        self.device.sleep(1.0)
        
        # 3. Click Orange (点击橙色按钮 - 搜索/攻击)
        if not self.device.click(self.IMG_BTN_ORANGE): return False
        self.device.sleep(1.0)
        
        # 4. Check Stamina (检查体力, 默认10点)
        req_stamina = 10 
        stamina_check = self.check_stamina_sufficient(req_stamina)
        
        if stamina_check == "RESTART":
            return "RESCAN"
            
        if isinstance(stamina_check, int) and not isinstance(stamina_check, bool):
            # 这里之前的日志 key 可能也是 log_intel_beast_stamina_low，保持一致即可
            self.logger.info(get_text("log_intel_beast_stamina_low")) 
            
            # [新增] 尝试自救
            if self._try_rescue_stamina():
                return "RESCAN"
            
            # [旧逻辑]
            delay_min = max(1, stamina_check * 5)
            self.set_next_run(seconds=delay_min * 60)
            self.device.ensure_home()
            return False
            
        # 5. Calculate Cost (计算戴安娜减耗)
        cost = self.calculate_cost(mode="wild")
        
        # 6. Click Equal (点击均兵)
        if not self.device.click(self.IMG_EQUAL): return False
        self.device.sleep(1.0)
        
        # 7. Click Blue2 (March) (点击出击 - 使用固定坐标区域)
        # Region: (546, 1213)
        self.device.click((546, 1213))
        self.device.sleep(2.0)
        
        # 8. Check Home (Success) (验证是否返回地图或主页)
        if self.device.exists(self.IMG_INTEL_ICON) or self.device.exists(self.IMG_BTN_TOWN):
            # Success
            self._update_stats(cost=cost, queue=1)
            
            # Check Queue After
            if self.data.get_stat("sidebar.idle_queues", 0) == 0:
                self.logger.info(get_text("log_intel_beast_queue_full"))
                self.set_next_run(seconds=300)
                self.device.ensure_home()
                return False
                
            return True
        else:
            self.logger.error("Event attack failed to return to map.")
            self.device.ensure_home()
            return False

    def _update_stats(self, cost=0, queue=0):
        if cost > 0:
            current_stamina = self.data.get_stat("stamina", 0)
            new_stamina = max(0, current_stamina - cost)
            self.data.set_stat("stamina", new_stamina)
            self.logger.info(get_text("log_intel_deduct_stamina", cost, new_stamina))

        if queue > 0:
            current_idle = self.sidebar.idle_march_count
            new_idle = max(0, current_idle - queue)
            self.data.set_stat("sidebar.idle_queues", new_idle)
            self.sidebar.idle_march_count = new_idle
            self.logger.info(get_text("log_intel_deduct_queue", queue, new_idle))

    def _try_rescue_stamina(self):
        """
        借用 StaminaControlTask 的逻辑来尝试领取免费体力。
        """
        self.logger.info("Attempting to rescue stamina using StaminaControlTask logic...")
        
        # 1. 实例化体力任务对象 (借用它的资源和方法)
        # 注意：这里只是创建对象，不会执行它的 run_impl
        helper = StaminaControlTask(self.device, self.data)
        
        # 2. 获取时间窗口信息 (直接复用 helper 的逻辑)
        current_tag, _, is_window_active = helper._get_current_period_info()
        
        if not is_window_active:
            self.logger.info("Not in free stamina claim window.")
            return False

        # 3. 检查本地记录 (双重检查)
        last_claimed = self.data.get_stat("tasks.StaminaControlTask.last_claimed_tag", "")
        if last_claimed == current_tag:
            self.logger.info(get_text("log_stamina_already_claimed"))
            return False

        # 4. 进入体力界面 (复用 helper 的导航逻辑)
        if not helper._enter_stamina_view():
            self.logger.warning("Failed to enter stamina view.")
            return False

        # 5. 视觉检查 (复用 helper 的 check.png 识别)
        if helper._check_is_claimed():
            self.logger.info("Visual check: Already claimed.")
            helper._mark_as_claimed(current_tag)
            self.device.ensure_home()
            return False

        # 6. 执行领取 (复用 helper 的点击逻辑)
        helper._perform_claim_click()
        helper._mark_as_claimed(current_tag)
        
        # 7. 更新体力并返回主页
        self.update_stamina()
        self.device.ensure_home()
        
        self.logger.info("Stamina rescued successfully!")
        return True