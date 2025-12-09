import time
import cv2
import numpy as np
from datetime import datetime, timezone, timedelta
from airtest.core.api import Template

from tasks.combat.combat_task import CombatTask
from tasks.combat.wolf import WolfTask
from game.map_searcher import MapSearcher
from i18n.i18n import get_text

class StaminaControlTask(CombatTask):
    # =========================================================================
    # 1. UI 配置定义
    # =========================================================================
    config_schema = [
        {"key": "enable", "type": "checkbox", "default": False, "menu": "Daily"},
        {"key": "dump_method", "default": "beast"},
        {"key": "dump_level", "default": 25},
        {"key": "dump_one_soldier", "default": True},
        {"key": "reserve_stamina", "default": 190},
        {"key": "hero_mode", "default": "diana_fahd"}
    ]

    @property
    def name(self):
        return "StaminaControlTask"

    @property
    def priority(self):
        return 30 

    def __init__(self, device, data):
        super().__init__(device, data)
        
        # --- 资源加载 ---
        self.IMG_PLUS = Template(r"assets/images/stamina/plus.png", threshold=0.9)
        self.IMG_PAGE_TITLE = Template(r"assets/images/stamina/stamina.png", threshold=0.9)
        self.IMG_CHECK = Template(r"assets/images/stamina/check.png", threshold=0.9, rgb=True)
        self.IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)

        # --- 常量定义 ---
        self.CLAIM_THRESHOLD = 70  
        self.PANIC_MINUTES = 15    
        
        # --- 时间参数 (严格 Mermaid B) ---
        self.WAIT_BEAST = 180    # 打野回城快: 3分钟
        self.WAIT_RALLY = 480    # 集结5分钟+回城: 8分钟
        self.WAIT_NO_QUEUE = 300 # 等待队列回城: 5分钟

    # =========================================================================
    # 2. 任务主入口 (严格遵循 Mermaid B 流程)
    # =========================================================================
    def run_impl(self):
        self.logger.info(f"=== {get_text('task_staminacontroltask')} Start (Step-by-Step Mode) ===")

        # [节点: Update_Start] 动作: OCR 更新当前体力
        self.logger.info(get_text("log_stamina_action_update"))
        if not self.update_stamina():
            self.logger.warning(get_text("log_stamina_ocr_fail"))
            self.set_next_run(seconds=300)
            return False
        
        current_stamina = self.data.get_stat("stamina", 0)

        # [节点: Init] 获取当前时间窗口信息
        current_tag, seconds_left, is_window_active = self._get_current_period_info()
        minutes_left = seconds_left / 60.0
        
        # [节点: CheckJSON] 本地记录是否已领?
        last_claimed = self.data.get_stat("tasks.StaminaControlTask.last_claimed_tag", "")
        is_claimed_local = (last_claimed == current_tag)

        self.logger.info(f"[Stamina] Tag: {current_tag} | Mins: {int(minutes_left)} | Active: {is_window_active} | Local Claimed: {is_claimed_local}")

        # === 流程分支判定 ===
        
        # 分支 1: 进入 [领奖突击模式] (Mode_Claim)
        # 条件: 窗口期内 AND 本地记录没领
        if is_window_active and not is_claimed_local:
            self.logger.info(get_text("log_stamina_mode_claim"))
            
            # [节点: NavUI] 进入体力页面
            if not self._enter_stamina_view():
                self.logger.error(get_text("log_stamina_enter_fail"))
                return False # 下次重试
                
            # [节点: CheckImg] 视觉检查 check.png
            self.logger.info(get_text("log_stamina_check_visual"))
            if self._check_is_claimed():
                # [节点: WriteJSON] 修正记录
                self.logger.info(get_text("log_stamina_already_claimed"))
                self._mark_as_claimed(current_tag)
                # 视觉已领 -> 转入 [日常维护模式]
                self.device.ensure_home()
                # 这里不 return，直接往下走去 CheckFull
            else:
                # [节点: CheckImg = 否] 真没领 -> 执行领奖逻辑
                return self._handle_claim_logic(current_stamina, current_tag, minutes_left)

        # 分支 2: 进入 [日常维护模式] (Mode_Maint)
        # 条件: 不在窗口期 OR 本地已领 (代码流转到这里)
        self.logger.info(get_text("log_stamina_mode_maint"))
        
        # 刷新一下 current_stamina (因为上面可能刚刚发生了领奖或 OCR)
        current_stamina = self.data.get_stat("stamina", 0)
        
        # [节点: CheckFull] 体力 > 190? (或者用户设置的阈值)
        target = self.data.get_cfg("modules.staminacontroltask.reserve_stamina", 190)
        
        if current_stamina > target:
            # [节点: A2] 体力高 -> 单步泄洪
            self.logger.info(get_text("log_stamina_high_dump", current_stamina, target))
            return self._execute_single_dump_step()
        else:
            # [节点: A1] 体力不高 -> 计算休息时间
            return self._calc_smart_wait(current_stamina, target, seconds_left)

    # =========================================================================
    # 3. 领奖逻辑分支 (Mode_Claim)
    # =========================================================================
    def _handle_claim_logic(self, current_stamina, current_tag, minutes_left):
        """
        对应 Mermaid B 的 [模式 B: 领奖突击]
        """
        # [节点: CheckPanic] 熔断期 < 15分钟?
        is_panic = minutes_left < self.PANIC_MINUTES
        
        if is_panic:
            # [节点: B1] 熔断 -> 直接领
            self.logger.warning(get_text("log_stamina_panic", int(minutes_left)))
            return self._perform_claim_sequence(current_tag)
        
        # [节点: CheckStamina] 体力 <= 70?
        if current_stamina <= self.CLAIM_THRESHOLD:
            # [节点: B3] 达标 -> 领奖
            self.logger.info(get_text("log_stamina_safe_claim", current_stamina))
            return self._perform_claim_sequence(current_tag)
        else:
            # [节点: B4] 未达标 -> 单步泄洪 (目标是降到70)
            self.logger.info(get_text("log_stamina_need_dump", current_stamina, self.CLAIM_THRESHOLD))
            self.device.ensure_home() 
            # 注意：这里调用的是单步泄洪，也就是说，打完一次怪它会退出去休息几分钟再回来
            # 直到体力降到 70 以下，这符合 Mermaid B "打一下动一下" 的逻辑
            return self._execute_single_dump_step()

    def _perform_claim_sequence(self, current_tag):
        """
        对应 Mermaid B 的 [4. 领奖后处理]
        Claim -> Mark -> OCR Update -> CheckFull -> Smart Wait / Dump
        """
        # [节点: Claim_Action]
        self._perform_claim_click()
        
        # [节点: MarkTrue]
        self._mark_as_claimed(current_tag)
        self.device.ensure_home()
        
        # [节点: Update_Post] 动作: OCR 再次更新体力
        self.logger.info(get_text("log_stamina_action_update"))
        
        if not self.update_stamina():
            # OCR 失败兜底：手动 +120，然后短时间重试
            current = self.data.get_stat("stamina", 0)
            self.data.set_stat("stamina", current + 120)
            self.set_next_run(seconds=60) 
            return True

        # 读取最新的体力
        new_stamina = self.data.get_stat("stamina", 0)
        target = self.data.get_cfg("modules.staminacontroltask.reserve_stamina", 190)
        
        # [节点: CheckFull] 检查是否溢出
        if new_stamina > target:
            self.logger.info(get_text("log_stamina_high_dump", new_stamina, target))
            # [节点: P2] 立即泄洪
            return self._execute_single_dump_step()
        
        # [核心修复] 如果不需要泄洪，计算智能休眠时间，而不是默认1小时
        self.logger.info(get_text("log_stamina_target_hit")) # "体力达标"
        
        # 获取 seconds_left 传给智能等待函数
        _, seconds_left, _ = self._get_current_period_info()
        
        # 转入智能休眠计算 (目标值-当前值)*5
        return self._calc_smart_wait(new_stamina, target, seconds_left)

    # =========================================================================
    # 4. 单步泄洪逻辑 (Dump - Step by Step)
    # =========================================================================
    def _execute_single_dump_step(self):
        """
        对应 Mermaid B 的 [P2 -> CheckQ -> Dump_Method -> Next_Wait]
        执行 **一次** 攻击，然后根据攻击类型设置推迟时间。
        """
        method = self.data.get_cfg("modules.staminacontroltask.dump_method", "beast")
        
        # [节点: CheckQ] 检查空闲队列
        self.device.ensure_home()
        idle_queues = self.sidebar.get_idle_march_queues()
        
        if idle_queues <= 0:
            # [节点: Next_Wait_Q] 无队列 -> 设置下次: 5分钟
            self.logger.warning(get_text("log_stamina_no_queues"))
            self.set_next_run(seconds=self.WAIT_NO_QUEUE)
            return True # 任务算执行成功（逻辑上的成功），只是在等待

        # 使用标准日志格式
        self.logger.info(get_text("log_stamina_dump_start", method, "1 Step")) 
        
        success, actual_cost = False, 0
        
        # 执行对应动作
        if method == "wolf":
            success, actual_cost = self._dump_with_wolf()
        elif method == "beast":
            success, actual_cost = self._dump_with_map_search("beast")
        elif method == "rally":
            success, actual_cost = self._dump_with_map_search("rally") 
        
        # 处理结果与时间设置
        if success:
            # 扣除数据 (更新内存)
            current = self.data.get_stat("stamina", 0)
            self.data.set_stat("stamina", max(0, current - actual_cost))
            self.data.set_stat("sidebar.idle_queues", max(0, idle_queues - 1))
            
            # [节点: Next_Rally / Next_Beast] 根据类型设置等待时间
            if method == "beast":
                wait_time = self.WAIT_BEAST # 3分钟
            else:
                # Wolf 和 Rally 都是集结类，等待时间长
                wait_time = self.WAIT_RALLY # 8分钟
                
            # 这里调用了新的 Key: log_stamina_step_wait
            self.logger.info(get_text("log_stamina_step_wait", method, int(wait_time/60)))
            self.set_next_run(seconds=wait_time)
            return True
        else:
            # 失败处理 (保持 60s 重试)
            self.logger.error(get_text("err_dump_failed"))
            self.set_next_run(seconds=60)
            return False

    # =========================================================================
    # 5. 智能休眠计算 (Calc_Next_Wait)
    # =========================================================================
    def _calc_smart_wait(self, current_stamina, target, seconds_to_refresh):
        """
        [节点: Calc_Next_Wait]
        计算逻辑: Min(体力回满时间, 距离下次刷新90分钟前的时间)
        """
        # A. 计算体力回满时间
        # 1点体力 = 5分钟 (300秒)
        needed = target - current_stamina
        if needed <= 0:
            wait_stamina = 300 # 已满，默认检查间隔
        else:
            wait_stamina = needed * 300
            
        # B. 计算距离下次领奖窗口开启的时间
        # 窗口是刷新前90分钟。所以我们要在 (刷新时间 - 90分钟) 的时候醒来
        wait_refresh = seconds_to_refresh - (90 * 60)
        
        if wait_refresh < 0:
            # 如果已经过了窗口期开始点，但我们不需要领奖（因为已经在维护模式了），那这个值就没意义了
            wait_refresh = 999999 

        # 取最小值，但至少睡 5 分钟
        wait_seconds = max(300, min(wait_stamina, wait_refresh))
        
        self.logger.info(get_text("log_stamina_sleep_calc", int(wait_seconds/60)))
        self.set_next_run(seconds=wait_seconds)
        return True

    # =========================================================================
    # 6. 具体执行动作 (保持不变)
    # =========================================================================

    def _enter_stamina_view(self):
        self.device.ensure_home()
        self.logger.info(get_text("log_action_click_avatar"))
        self.device.click((61, 38))
        self.device.sleep(1.0)
        
        if self.device.exists(self.IMG_PLUS):
            self.logger.info(get_text("log_action_click_plus"))
            self.device.click(self.IMG_PLUS)
            self.device.sleep(1.5)
        else:
            self.logger.warning(get_text("err_plus_not_found"))
            return False
            
        return self._is_in_stamina_view()

    def _is_in_stamina_view(self):
        area = (36, 340, 161, 456)
        screen_path = self.device.snapshot()
        if not screen_path: return False
        
        img = cv2.imread(screen_path)
        if img is None: return False
        
        crop = img[area[1]:area[3], area[0]:area[2]]
        res = self.IMG_PAGE_TITLE.match_in(crop)
        return (res is not None)

    def _check_is_claimed(self):
        return self.device.exists(self.IMG_CHECK)

    def _perform_claim_click(self):
        # 纯点击动作，不含逻辑
        if not self._is_in_stamina_view():
            if not self._enter_stamina_view():
                return False
        
        self.logger.info(get_text("log_action_claiming"))
        target_pos = (602, 407)
        
        self.device.click(target_pos)
        time.sleep(0.4)
        self.device.click(target_pos)
        self.device.sleep(2.0)
        return True

    def _mark_as_claimed(self, tag):
        self.data.set_stat("tasks.StaminaControlTask.last_claimed_tag", tag)
        self.logger.info(get_text("log_stamina_mark_saved", tag))

    def _get_current_period_info(self):
        now_utc = datetime.now(timezone.utc)
        refresh_00 = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        refresh_12 = now_utc.replace(hour=12, minute=0, second=0, microsecond=0)
        refresh_24 = refresh_00 + timedelta(days=1)
        
        if now_utc < refresh_12:
            current_tag = now_utc.strftime("%Y%m%d_00")
            target_refresh = refresh_12
        else:
            current_tag = now_utc.strftime("%Y%m%d_12")
            target_refresh = refresh_24
            
        seconds_left = (target_refresh - now_utc).total_seconds()
        # minutes_left = seconds_left / 60
        is_window_active = (seconds_left <= 90 * 60) # 90分钟
        
        return current_tag, seconds_left, is_window_active

    def _perform_hero_selection(self):
        """通用选将逻辑"""
        hero_mode = self.data.get_cfg("modules.staminacontroltask.hero_mode", "diana_fahd")
        targets = []
        if hero_mode == "diana": targets = ["diana"]
        elif hero_mode == "diana_fahd": targets = ["diana", "fahd"]
        
        if targets:
            try:
                self.select_heroes(targets)
            except Exception as e:
                self.logger.warning(get_text("err_hero_select", e))
                return False
        return True

    def _perform_attack(self):
        """点击蓝色按钮出击并验证"""
        self.device.click(self.IMG_BTN_BLUE)
        self.device.sleep(1.0)
        return self.verify_attack_success()

    def _dump_with_wolf(self):
        """Wolf 流程: 找狼 -> 选将 -> 设兵 -> 计算 -> 出击"""
        wolf_task = WolfTask(self.device, self.data)
        if not wolf_task.find_and_click_wolf():
            return False, 0
            
        try:
            self.verify_combat_page()
        except:
            return False, 0
            
        if not self._perform_hero_selection():
            return False, 0
            
        use_one_soldier = self.data.get_cfg("modules.staminacontroltask.dump_one_soldier", True)
        if use_one_soldier:
            self.set_one_soldier(True)
        else:
            self.set_one_soldier(False)
            
        real_cost = self.get_realtime_cost(mode="rally")
            
        if self._perform_attack():
            return True, real_cost
        else:
            return False, 0

    def _dump_with_map_search(self, mode):
        """Beast/Rally 流程: 搜怪 -> 选将 -> [新增:强制均兵] -> 计算 -> 出击"""
        level = self.data.get_cfg("modules.staminacontroltask.dump_level", 25)
        searcher = MapSearcher(self.device, self.data)
        search_key = "terror" if mode == "rally" else "beast"
        
        # 1. 搜索
        if not searcher.run(search_key, level):
            return False, 0
            
        # 2. 验证页面
        try:
            self.verify_combat_page()
        except:
            return False, 0
            
        # 3. 选将
        self._perform_hero_selection()
        
        # === [新增] 4. 强制均兵 (Equal) ===
        # 无论之前配置如何，打野和集结必须带兵，不能是1兵
        # set_one_soldier(False) 的内部实现就是点击 "Equal" 按钮
        self.logger.info(get_text("log_set_avg_soldier"))
        self.set_one_soldier(False) 
        # ================================

        # 5. 计算实时消耗
        cost_mode = "rally" if mode == "rally" else "wild"
        real_cost = self.get_realtime_cost(mode=cost_mode)
            
        # 6. 出击
        if self._perform_attack():
            return True, real_cost
        else:
            return False, 0