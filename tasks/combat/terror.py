# tasks/combat/rally.py
# -*- coding: utf-8 -*-

from tasks.combat.combat_task import CombatTask
from game.map_searcher import MapSearcher
from i18n.i18n import get_text
from airtest.core.api import Template
import math

class RallyTask(CombatTask):
    # =========================================================================
    # 1. UI 配置定义
    # =========================================================================
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable", 
            "default": False,
            "menu": "Combat"
        },
        {
            "key": "target_level",
            "type": "spinbox",
            "label": "cfg_target_level", 
            "min": 1,
            "max": 7, # 巨兽等级通常较低 (1-7)
            "default": 1
        },
        {
            "key": "remaining_attacks",
            "type": "spinbox",
            "label": "cfg_remaining_attacks", 
            "min": 0,
            "max": 100,
            "default": 3 # 巨兽次数通常较少
        },
        {
            "key": "concurrent_queues",
            "type": "spinbox",
            "label": "cfg_concurrent_queues",
            "min": 1,
            "max": 6,
            "default": 1
        },
        {
            "key": "hero_mode",
            "type": "combobox",
            "label": "cfg_hero_mode",
            "options": [
                {"value": "any", "label": "opt_hero_any"},
                {"value": "diana", "label": "opt_hero_diana"},
                {"value": "diana_fahd", "label": "opt_hero_fahd_diana"}
            ],
            "default": "any"
        },
        {
            "key": "soldier_mode",
            "type": "combobox",
            "label": "cfg_soldier_mode",
            "options": [
                {"value": "full", "label": "opt_soldier_full"},
                {"value": "equal", "label": "opt_soldier_equal"}
            ],
            "default": "full"
        }
    ]

    @property
    def name(self):
        return "RallyTask"

    @property
    def priority(self):
        return 45 # 优先级略高于打野怪

    @property
    def default_interval(self):
        return 480 # 默认 10 分钟 (因为集结本身需要5分钟等待)

    def run_impl(self):
        # =====================================================================
        # 阶段 1: 读取配置 (Load Config)
        # =====================================================================
        # 注意: key 是 modules.rallytask.*
        target_level = self.data.get_cfg("modules.rallytask.target_level", 1)
        remaining = self.data.get_cfg("modules.rallytask.remaining_attacks", 0)
        user_queue_limit = self.data.get_cfg("modules.rallytask.concurrent_queues", 1)
        hero_mode = self.data.get_cfg("modules.rallytask.hero_mode", "any")
        soldier_mode = self.data.get_cfg("modules.rallytask.soldier_mode", "full")

        # 检查剩余次数
        if remaining <= 0:
            self.logger.info(get_text("log_task_finished_zero_rem", self.name))
            self.data.set_cfg("modules.rallytask.enable", False)
            return False

        self.logger.info(get_text("log_rally_start_round", remaining, target_level))

        # =====================================================================
        # 阶段 2: 前置环境与资源检查 (Pre-Check Logic)
        # =====================================================================
        
        # 2.1 确保在主页
        self.device.ensure_home()

        # 2.2 获取游戏内实际空闲队列
        game_idle_queues = self.sidebar.get_idle_march_queues()
        
        # 2.3 OCR 更新体力
        if not self.update_stamina():
            self.logger.warning(get_text("log_stamina_read_fail_skip"))
            return False
        
        current_stamina = self.data.get_stat("stamina", 0)

        # =====================================================================
        # 阶段 3: 计算本轮执行批次 (Calc Batch Size)
        # =====================================================================
        
        # A. 队列限制
        adjusted_queue_limit = min(user_queue_limit, game_idle_queues)
        
        # B. 英雄限制
        if hero_mode in ["diana", "diana_fahd"]:
            adjusted_queue_limit = 1
            self.logger.info(get_text("log_hero_mode_limit_queue"))

        # C. 体力限制 (与 Beast 的主要区别)
        diana_skill_lv = self.data.get_cfg("modules.general.diana_level", 0)
        
        # 获取单次集结消耗 (默认25)
        unit_cost = 25
        if hero_mode in ["diana", "diana_fahd"] and diana_skill_lv > 0:
            # 查表: DIANA_COST_TABLE[lv][0] 是集结消耗
            unit_cost = self.DIANA_COST_TABLE.get(diana_skill_lv, (25, 10))[0] 
        
        available_stamina = self.get_disposable_stamina(current_stamina)
        possible_by_stamina = available_stamina // unit_cost

        # --- 最终计算 Batch Size ---
        batch_size = min(adjusted_queue_limit, possible_by_stamina, remaining)

        # 详细日志
        self.logger.info(get_text("log_batch_calc_detail", 
                                  user_queue_limit, game_idle_queues, current_stamina, remaining, batch_size))

        # =====================================================================
        # 阶段 4: 批次有效性检查与等待逻辑 (Wait Logic)
        # =====================================================================
        if batch_size <= 0:
            # 4.1 原因：没队列
            if adjusted_queue_limit == 0:
                self.logger.warning(get_text("log_no_idle_queues_wait"))
                self.set_next_run(seconds=180) # 3分钟后重试
                return False
            
            # 4.2 原因：没体力
            if possible_by_stamina == 0:
                missing_stamina = unit_cost - current_stamina
                wait_seconds = missing_stamina * 300 # 5分钟/点
                wait_minutes = math.ceil(wait_seconds / 60)
                self.logger.warning(get_text("log_stamina_wait", current_stamina, unit_cost, wait_minutes))
                self.set_next_run(seconds=wait_seconds)
                return False
                
            return False

        # =====================================================================
        # 阶段 5: 内部循环执行 (Execution Loop)
        # =====================================================================
        searcher = MapSearcher(self.device, self.data)
        success_count = 0
        
        # 出击按钮 (蓝色) - 集结也是点这个
        IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)
        
        self.logger.info(get_text("log_batch_start", batch_size))

        for i in range(batch_size):
            self.logger.info(get_text("log_processing_batch", i+1, batch_size))
            
            # 5.1 地图搜索 (参数 "terror")
            # MapSearcher 内部会自动处理 "搜索 -> 点击橙色 -> 点击集结" 的逻辑
            if not searcher.run("terror", target_level):
                self.logger.error(get_text("err_map_search_failed"))
                break
            
            # 5.2 确保在战斗界面
            try:
                self.verify_combat_page()
            except Exception:
                self.logger.error(get_text("err_combat_page_failed"))
                break

            # 5.3 选将逻辑
            target_heroes = []
            if hero_mode == "diana":
                target_heroes = ["diana"]
            elif hero_mode == "diana_fahd":
                target_heroes = ["diana", "fahd"]
            
            try:
                self.select_heroes(target_heroes)
            except Exception as e:
                self.logger.warning(get_text("err_hero_busy_skip", e))
                break

            # 5.4 兵力设置
            if soldier_mode == "equal":
                self.logger.info(get_text("log_clicking_equal"))
                self.device.click(self.IMG_EQUAL)
                self.device.sleep(0.5)
            else:
                pass

            real_time_cost = self.get_realtime_cost(mode="rally")
            
            if current_stamina < real_time_cost:
                self.logger.warning(get_text("log_stamina_insufficient_final", current_stamina, real_time_cost, 0))
                break

            # 5.5 出击 (Dispatch)
            self.logger.info(get_text("log_dispatching"))
            self.device.click(IMG_BTN_BLUE)
            self.device.sleep(1.0)
            
            if self.verify_attack_success():
                success_count += 1
                
                # 5.6 内存数据更新 (Update Data)
                remaining -= 1
                self.data.set_cfg("modules.rallytask.remaining_attacks", remaining)
                
                # 更新本地体力记录 (使用当前任务计算出的消耗)
                current_stamina = max(0, current_stamina - real_time_cost)
                self.data.set_stat("stamina", current_stamina)
                
                # 更新空闲队列
                game_idle_queues -= 1
                
            else:
                self.logger.error(get_text("err_attack_verify_fail"))
                break
                
            # 循环继续...

        # =====================================================================
        # 阶段 6: 善后处理 (Post Loop)
        # =====================================================================
        self.logger.info(get_text("log_batch_finished", success_count))
        
        # 6.1 保存数据
        self.data.save_config()
        self.data.save_stats()

        if remaining <= 0:
            self.logger.info(get_text("log_task_done_disable", self.name))
            # 禁用任务
            self.data.set_cfg("modules.rallytask.enable", False)
            self.data.save_config()
            return True
        
        # 6.2 设置下次运行时间 (回城等待)
        # 集结等待逻辑：固定集结等待(5min=300s) + 行军战斗回城(约3min=180s)
        # 基础等待 480秒，每多一队稍微加一点缓冲
        wait_time = 420 + (success_count * 5)
        
        self.logger.info(get_text("log_waiting_return", wait_time))
        self.set_next_run(seconds=wait_time)
        
        # 6.3 确保回到主页
        self.device.ensure_home()
        
        return True