from tasks.base_task import BaseTask
from game.troop_manager import TroopManager, TroopType, TrainMode
from i18n.i18n import get_text
from datetime import datetime, timedelta
import time

class TroopTrainingTask(BaseTask):
    
    # =========================================================================
    # UI 配置定义
    # =========================================================================
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable",
            "default": False,
            "menu": "Daily"
        },
        # --- 1. 步兵 (Infantry) ---
        {"key": "sep_infantry", "type": "separator", "label": "lbl_infantry_settings"},
        {"key": "infantry_enable", "type": "checkbox", "label": "lbl_enable_troop", "default": False},
        {"key": "infantry_max_level", "type": "spinbox", "label": "cfg_max_unlock_level", "min": 1, "max": 10, "default": 10},
        {
            "key": "infantry_mode",
            "type": "combobox",
            "label": "cfg_train_mode",
            "options": [
                {"value": "train", "label": "opt_mode_train_new"},
                {"value": "promote", "label": "opt_mode_promote"}
            ],
            "default": "train"
        },
        {"key": "infantry_target_level", "type": "spinbox", "label": "cfg_operate_level", "min": 1, "max": 10, "default": 9},

        # --- 2. 骑兵 (Lancer) ---
        {"key": "sep_lancer", "type": "separator", "label": "lbl_lancer_settings"},
        {"key": "lancer_enable", "type": "checkbox", "label": "lbl_enable_troop", "default": False},
        {"key": "lancer_max_level", "type": "spinbox", "label": "cfg_max_unlock_level", "min": 1, "max": 10, "default": 10},
        {
            "key": "lancer_mode",
            "type": "combobox",
            "label": "cfg_train_mode",
            "options": [
                {"value": "train", "label": "opt_mode_train_new"},
                {"value": "promote", "label": "opt_mode_promote"}
            ],
            "default": "train"
        },
        {"key": "lancer_target_level", "type": "spinbox", "label": "cfg_operate_level", "min": 1, "max": 10, "default": 9},

        # --- 3. 弓兵 (Marksman) ---
        {"key": "sep_marksman", "type": "separator", "label": "lbl_marksman_settings"},
        {"key": "marksman_enable", "type": "checkbox", "label": "lbl_enable_troop", "default": False},
        {"key": "marksman_max_level", "type": "spinbox", "label": "cfg_max_unlock_level", "min": 1, "max": 10, "default": 10},
        {
            "key": "marksman_mode",
            "type": "combobox",
            "label": "cfg_train_mode",
            "options": [
                {"value": "train", "label": "opt_mode_train_new"},
                {"value": "promote", "label": "opt_mode_promote"}
            ],
            "default": "train"
        },
        {"key": "marksman_target_level", "type": "spinbox", "label": "cfg_operate_level", "min": 1, "max": 10, "default": 9},

        # --- 4. 时间设置 ---
        {"key": "sep_time", "type": "separator", "label": "lbl_time_settings"},
        {"key": "train_time_h", "type": "spinbox", "label": "cfg_train_time_h", "min": 0, "max": 24, "default": 3},
        {"key": "train_time_m", "type": "spinbox", "label": "cfg_train_time_m", "min": 0, "max": 59, "default": 0}
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        self.manager = TroopManager(device, data)

    @property
    def name(self):
        return "TroopTrainingTask"

    @property
    def priority(self):
        return 55

    @property
    def default_interval(self):
        return 3600

    def run_impl(self):
        self.logger.info(get_text("task_trooptrainingtask") + " Started")
        
        # 1. 尝试进入兵营
        self.device.ensure_home()
        
        if not self.manager.enter_barracks():
            self.logger.warning("Entry failed. Postponing task.")
            self.sidebar.collapse()
            self.device.ensure_home()
            self.set_next_run(seconds=300)
            return False

        # 2. 任务定义
        tasks = [
            (TroopType.INFANTRY, "infantry"),
            (TroopType.CAVALRY,  "lancer"),
            (TroopType.ARCHER,   "marksman")
        ]
        
        # 获取用户设置的训练时长
        user_h = self.data.get_cfg("modules.trooptrainingtask.train_time_h", 3)
        user_m = self.data.get_cfg("modules.trooptrainingtask.train_time_m", 0)
        user_duration_sec = user_h * 3600 + user_m * 60
        if user_duration_sec < 300: user_duration_sec = 300 

        # 3. 循环处理
        for t_type, prefix in tasks:
            # A. 检查启用
            is_enabled = self.data.get_cfg(f"modules.trooptrainingtask.{prefix}_enable", False)
            if not is_enabled:
                continue

            # B. 切换页签
            if not self.manager.switch_to_tab(t_type):
                self.logger.warning(f"Failed to switch to {t_type}")
                continue

            # C. 检查状态
            is_busy_initially = (self.manager.check_state() == "busy")
            training_just_started = False
            
            if is_busy_initially:
                self.logger.info(f"{t_type} is busy (Training in progress).")
                # 忙碌状态下，不更新时间戳，沿用上次记录
            else:
                # D. 空闲 -> 执行流程
                mode = self.data.get_cfg(f"modules.trooptrainingtask.{prefix}_mode", "train")
                
                # 注意：target_level 是多义词。Train模式是目标等级，Promote模式是来源等级。
                level = self.data.get_cfg(f"modules.trooptrainingtask.{prefix}_target_level", 9)
                
                # E. 选兵
                if not self.manager.select_tier(level):
                    continue
                    
                # F. 执行
                result = False
                if mode == "train":
                    result = self.manager.execute_train_action()
                else:
                    # === 晋升模式 ===
                    code = self.manager.execute_promote_action()
                    
                    if code == "NO_PROMOTABLE":
                        # === [核心功能] 自动降级逻辑 ===
                        self.logger.info(f"No promotable troops. Fallback to Train New.")
                        
                        # 1. 获取 Fallback 等级 (Max - 1)
                        max_level = self.data.get_cfg(f"modules.trooptrainingtask.{prefix}_max_level", 10)
                        fallback_level = max(1, max_level - 1)
                        
                        self.logger.info(f"Fallback: Selecting T{fallback_level} to train.")
                        
                        # 2. 重新选兵
                        if self.manager.select_tier(fallback_level):
                            # 3. 执行普通训练
                            result = self.manager.execute_train_action()
                            if result:
                                self.logger.info(f"Fallback training success.")
                        else:
                            self.logger.warning("Fallback selection failed.")
                            
                    else:
                        result = code

                if result:
                    self.logger.info(f"{t_type} action started.")
                    training_just_started = True

            # === 更新时间戳 ===
            # 无论是正常的训练/晋升，还是降级后的训练，只要成功了，都更新时间
            if training_just_started:
                finish_time = datetime.now() + timedelta(seconds=user_duration_sec)
                self._save_finish_time(prefix, finish_time)

        # 4. 退出
        self.manager.exit_barracks()

        # 5. 调度计算
        self._schedule_next_run(tasks)
        
        return True

    def _save_finish_time(self, prefix, dt_obj):
        """保存预计结束时间到 statistics"""
        ts_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        self.data.set_stat(f"tasks.TroopTrainingTask.{prefix}_finish_time", ts_str)

    def _get_finish_time(self, prefix):
        """读取预计结束时间"""
        ts_str = self.data.get_stat(f"tasks.TroopTrainingTask.{prefix}_finish_time", "")
        if not ts_str:
            return None
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except:
            return None

    def _schedule_next_run(self, tasks):
        """
        同步调度策略：
        1. 盲区检测：如果有兵种在忙但没记录时间，只睡 10 分钟。
        2. 节奏对齐：找出【最晚结束】的那个时间点，大家一起等它。
        """
        now = datetime.now()
        future_finish_times = []
        
        enabled_count = 0
        valid_future_record_count = 0

        for _, prefix in tasks:
            is_enabled = self.data.get_cfg(f"modules.trooptrainingtask.{prefix}_enable", False)
            if not is_enabled:
                continue
            
            enabled_count += 1
            f_time = self._get_finish_time(prefix)
            
            # 只有当记录的时间确实在未来（说明还在练），才纳入计算
            if f_time and f_time > now:
                future_finish_times.append(f_time)
                valid_future_record_count += 1
            
        # === 核心调度逻辑 ===
        
        if enabled_count == 0:
            # 没启用任何兵种，睡默认时间
            self.set_next_run(seconds=3600)
            return

        # 1. 盲区检测 (Blind Spot)
        # 如果 有效记录数 < 启用数
        # 意味着：有兵种是 Busy 状态，但我们不知道它具体啥时候结束
        # 必须短睡重试，试图捕获它的空闲瞬间
        if valid_future_record_count < enabled_count:
            self.logger.info("Sync pending: Waiting for unknown status troops. Checking in 10 mins.")
            self.set_next_run(seconds=600)
            return

        # 2. 同步对齐计算 (Sync Alignment - Max Strategy)
        if future_finish_times:
            # 取最大值：等最慢的那个练完
            target_time = max(future_finish_times)
            
            wait_seconds = (target_time - now).total_seconds()
            
            # 加上 10 分钟缓冲，确保那个最慢的也肯定好了
            wait_seconds += 600 
            
            # 最小安全间隔 (5分钟)
            wait_seconds = max(300, wait_seconds)
            
            wait_h = int(wait_seconds // 3600)
            wait_m = int((wait_seconds % 3600) // 60)
            self.logger.info(f"Sync Strategy: Aligning to latest troop. Sleep {wait_h}h {wait_m}m.")
            self.set_next_run(seconds=wait_seconds)
        else:
            # 所有兵营都闲着，或者记录的时间都在过去
            # 正常情况下 run_impl 会处理并更新，这里兜底
            self.set_next_run(seconds=600)