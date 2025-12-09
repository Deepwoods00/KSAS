from tasks.combat.combat_task import CombatTask
from i18n.i18n import get_text
from airtest.core.api import Template
from basic import TaskInterruptedError
import time

class WolfTask(CombatTask):
    # UI 配置定义
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable_wolf",
            "default": False,
            "menu": "Combat"
        },
        {
            "key": "interval",
            "type": "spinbox",
            "label": "cfg_wolf_interval",
            "min": 1,
            "max": 1440,
            "default": 450
        },
        {
            "key": "max_attacks",
            "type": "spinbox",
            "label": "cfg_wolf_attacks",
            "min": 1,
            "max": 100,
            "default": 10
        },
        {
            "key": "one_soldier",
            "type": "checkbox",
            "label": "cfg_wolf_one_soldier",
            "default": False
        },
        {
            "key": "heroes",
            "type": "combobox",
            "label": "cfg_wolf_hero",
            "options": [
                {"value": "none", "label": "opt_hero_any"},
                {"value": "diana", "label": "opt_hero_diana"},
                {"value": "diana_fahd", "label": "opt_hero_fahd_diana"}
            ],
            "default": "none"
        },
        {
            "key": "fallback_policy",
            "type": "combobox",
            "label": "cfg_wolf_fallback",
            "options": [
                {"value": "use_default", "label": "opt_fallback_default"},
                {"value": "wait_1h", "label": "opt_fallback_wait"} # UI显示叫Wait 1h，实际逻辑现在改为重试机制
            ],
            "default": "use_default"
        }
    ]
    
    @property
    def name(self):
        return "WolfTask"

    @property
    def priority(self):
        return 40

    @property
    def default_interval(self):
        # 默认 7分30秒
        return 450

    def run_impl(self):
        # 1. 读取配置
        use_one_soldier = self.data.get_cfg("modules.wolftask.one_soldier", False)
        hero_config = self.data.get_cfg("modules.wolftask.heroes", "none")
        fallback_policy = self.data.get_cfg("modules.wolftask.fallback_policy", "use_default")
        max_attacks = self.data.get_cfg("modules.wolftask.max_attacks", 10)
        interval = self.data.get_cfg("modules.wolftask.interval", 450)
        
        # 2. 检查剩余次数
        if max_attacks <= 0:
            self.logger.info(get_text("log_wolf_finished"))
            self.data.set_cfg("modules.wolftask.enable", False)
            return False # 停止执行

        self.logger.info(get_text("log_wolf_start", use_one_soldier, hero_config))

        # 3. 预检查 (Pre-Check)
        # 如果预检查失败，pre_check 内部会设置好 next_run 并返回 False
        if not self.pre_check(hero_config):
            return False

        # 4. 寻找与战斗配置循环 (处理 "验证页面失败 -> 重试" 的逻辑)
        # 外层循环处理 "RESTART" 信号 (体力更新后重启流程)
        max_restarts = 2
        restart_count = 0
        
        while restart_count < max_restarts:
            combat_ready = False
            
            # 对应流程图中 "CombatRetryCheck < 3" 的循环
            for attempt in range(3):
                # 4.1 寻找狼 (内部包含 3 次寻找重试)
                if not self.find_and_click_wolf():
                    # find_and_click_wolf 内部重试失败后返回 False
                    # 根据流程图，寻找失败直接结束
                    self.logger.warning(get_text("log_wolf_search_fail"))
                    return False

                # 4.2 验证是否在出击界面
                # 这里对应 "VerifyPage" 节点
                is_combat_page = False
                try:
                    self.verify_combat_page()
                    is_combat_page = True
                except TaskInterruptedError:
                    raise
                except:
                    is_combat_page = False
                
                if not is_combat_page:
                    self.logger.warning(get_text("log_wolf_combat_page_fail", attempt+1))
                    continue # 对应 "CombatRetryCheck -- 是 --> NavStart"
                
                # 4.3 战斗准备 (英雄 & 兵力)
                # 对应 "NeedHeroes", "SelectHeroes", "Fallback" 等逻辑
                if not self.prepare_combat_logic(use_one_soldier, hero_config, fallback_policy):
                    # 如果 prepare 返回 False，说明触发了 Wait 策略且次数未满
                    # 此时 next_run 已经被设置为 5 分钟后
                    return False
                
                # 如果成功准备好
                combat_ready = True
                break
            
            if not combat_ready:
                self.logger.error(get_text("log_wolf_combat_page_fail_final"))
                return False

            # 5. 发起集结 (Start Rally)
            rally_result = self.start_rally_logic()
            
            if rally_result == "RESTART":
                self.logger.info(get_text("log_wolf_restart_for_stamina"))
                restart_count += 1
                continue
            
            if rally_result is True:
                # === 数据更新 (Update Stats) ===
                # 成功发起集结，跳出 while 循环
                break
            else:
                # 返回 False (体力不足或其他错误)，直接结束
                return False
        
        # 如果循环结束是因为成功
        if rally_result is True:
            
            # A. 扣除剩余次数
            new_max = max(0, max_attacks - 1)
            self.data.set_cfg("modules.wolftask.max_attacks", new_max)
            self.logger.info(get_text("log_wolf_attacks_left", new_max))
            
            # B. 扣除体力 (统计数据)
            cost = self.get_actual_cost()
            current_stamina = self.data.get_stat("stamina", 0)
            new_stamina = max(0, current_stamina - cost)
            self.data.set_stat("stamina", new_stamina)
            
            # C. 扣除空闲队列 (统计数据)
            current_idle = self.sidebar.idle_march_count
            new_idle = max(0, current_idle - 1)
            self.data.set_stat("sidebar.idle_queues", new_idle)
            self.sidebar.idle_march_count = new_idle
            
            # D. 判断是否结束
            if new_max == 0:
                self.logger.info(get_text("log_wolf_disabled_zero_attacks"))
                self.data.set_cfg("modules.wolftask.enable", False)
                # 不设置下次运行，任务自然停止
            else:
                # E. 安排下一次运行
                # 显式调用 set_next_run，确保按照配置的 interval (如 450s) 运行
                self.set_next_run(seconds=interval)
                
            return True
        
        return False

    def pre_check(self, hero_config):
        """
        0. 预检查
        """
        # 0.1 Ensure Home
        self.device.ensure_home()

        # 0.2 Check Queue
        idle_queues = self.sidebar.get_idle_march_queues()
        if idle_queues <= 0:
            self.logger.warning(get_text("log_wolf_no_queue"))
            self.set_next_run(seconds=300)
            return False

        # 0.2.1 Update Stamina (新增步骤)
        self.logger.info(get_text("log_wolf_updating_stamina"))
        self.update_stamina()

        # 0.3 Check Stamina
        required_stamina = self.get_required_stamina(hero_config)
        current_stamina = self.data.get_stat("stamina", 0)
        available_stamina = self.get_disposable_stamina(current_stamina)
        
        self.logger.info(get_text("log_wolf_stamina_check", available_stamina, required_stamina))

        # 判定时使用 available_stamina
        if available_stamina < required_stamina:
            # 计算缺口 (注意：如果是因为被锁住了，这里会算出需要等待)
            # 例如: 当前100, 锁了75 -> 可用25. 需求30.
            # 缺口 = 30 - 25 = 5. 程序会进入等待，这正是我们想要的。
            missing = required_stamina - available_stamina
            wait_seconds = missing * 300
            
            self.logger.warning(get_text("log_wolf_stamina_gap", missing, missing * 5))
            self.set_next_run(seconds=wait_seconds)
            return False
        
        return True

    def find_and_click_wolf(self):
        """
        寻找狼牙棒，包含内部重试逻辑
        """
        IMG_BACKPACK = Template(r"assets/images/home/backpack.png", threshold=0.9)
        IMG_CHECK = Template(r"assets/images/wolf/check.png", threshold=0.9)
        IMG_WOLF = Template(r"assets/images/wolf/wolf.png", threshold=0.9)
        IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)
        IMG_BTN_ORANGE = Template(r"assets/images/btn/btn_orange.png", threshold=0.9)

        # 重试循环 (Retry < 3)
        for i in range(3):
            self.logger.info(f"寻找物品尝试 {i+1}/3")
            
            # 每次重试都先 Ensure Home (回路起点)
            self.device.ensure_home()

            # 1. 点击 backpack
            if not self.device.click(IMG_BACKPACK):
                self.logger.warning(get_text("log_wolf_backpack_fail"))
                continue
            self.device.sleep(0.5)

            # 2. 点击标签页
            self.device.click((630, 120))
            self.device.sleep(0.8)

            # 3. 检查 check.png
            if not self.device.exists(IMG_CHECK):
                self.logger.warning(get_text("log_wolf_check_fail"))
                continue
            
            # 4. 点击 wolf.png
            if not self.device.click(IMG_WOLF):
                self.logger.warning(get_text("log_wolf_icon_fail"))
                continue
            self.device.sleep(0.5)

            # 成功找到并点击，跳出循环进入下一步
            break
        else:
            # 循环正常结束说明3次都失败
            self.logger.error(get_text("log_wolf_item_fail"))
            return False

        # 后续操作 (点击使用 -> 搜索 -> 攻击)
        self.logger.info(get_text("log_wolf_click_use"))
        self.device.click(IMG_BTN_BLUE)
        self.device.sleep(1)

        self.logger.info(get_text("log_wolf_click_pos"))
        self.device.click((360, 570))
        self.device.sleep(0.5)

        self.logger.info(get_text("log_wolf_click_search"))
        self.device.click(IMG_BTN_ORANGE)
        self.device.sleep(1.5) # 等待跳转

        self.logger.info(get_text("log_wolf_click_rally"))
        self.device.sleep(1)
        if not self.device.click(IMG_BTN_BLUE):
            self.logger.warning(get_text("log_wolf_attack_btn_missing"))
            return False
        
        self.device.sleep(1.5)
        return True

    def prepare_combat_logic(self, use_one_soldier, hero_config, fallback_policy):
        """
        战斗配置核心逻辑 (包含英雄选将和失败策略)
        """
        # 解析需要选择的英雄
        target_heroes = []
        if hero_config == "diana":
            target_heroes = ["diana"]
        elif hero_config == "diana_fahd":
            target_heroes = ["diana", "fahd"]
            
        hero_selection_success = True
        
        if target_heroes:
            try:
                self.select_heroes(target_heroes)
                # [成功路径] 顺便重置计数
                self.data.set_runtime("wolf_hero_retry_count", 0)
            except TaskInterruptedError:
                raise
            except Exception as e:
                self.logger.warning(get_text("log_hero_selection_failed", e))
                hero_selection_success = False
                
                # [失败路径]
                if fallback_policy == "wait_1h": # UI上叫 Wait 1h，实际逻辑是有限重试
                    # 获取当前重试次数
                    retry_count = self.data.get_runtime("wolf_hero_retry_count", 0)
                    
                    if retry_count < 16:
                        # [情况 A] 次数未满: 推迟5分钟
                        new_count = retry_count + 1
                        self.data.set_runtime("wolf_hero_retry_count", new_count)
                        self.logger.warning(get_text("log_wolf_hero_retry", new_count))
                        
                        self.set_next_run(seconds=300)
                        return False # 结束本次运行
                    else:
                        # [情况 B] 次数耗尽: 强制执行
                        self.logger.error(get_text("log_wolf_hero_force"))
                        # 按 Back 键退出英雄选择界面 (如果有的话)，或者确保在出击界面
                        self.device.keyevent("BACK")
                        self.device.sleep(0.5)
                        # 继续往下执行 (Fall through)
                else:
                    # Default 策略: 直接按 Back 继续
                    self.logger.info(get_text("log_wolf_hero_default"))
                    self.device.keyevent("BACK")
                    self.device.sleep(0.5)
        
        # 检查兵力设置
        if use_one_soldier:
            self.set_one_soldier(True)
        else:
            self.set_one_soldier(False) # 显式设置为平均，防止上次残留
            
        return True

    def start_rally_logic(self):
        """
        发起集结逻辑 (包含体力检测)
        :return:
            - True: 成功发起
            - False: 失败 (体力不足或UI错误)
            - "RESTART": 需要重启流程 (体力更新后)
        """
        # 1. 体力检测
        # 获取实际消耗 (通常是 25 或戴安娜优惠值)
        cost = self.get_actual_cost()
        stamina_check = self.check_stamina_sufficient(cost)
        
        if stamina_check == "RESTART":
            return "RESTART"
            
        if isinstance(stamina_check, int): # missing stamina
            missing = stamina_check
            wait_seconds = max(300, missing * 300)
            self.logger.warning(get_text("log_wolf_stamina_warn", wait_seconds/60))
            self.set_next_run(seconds=wait_seconds)
            return False

        # stamina_check is True -> Proceed
        
        # 2. 点击出击
        IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)
        self.logger.info(get_text("log_wolf_click_attack"))
        
        if self.device.click(IMG_BTN_BLUE):
            self.device.sleep(1)
            # 3. 验证是否回到主页
            if self.verify_attack_success():
                return True
            else:
                self.logger.error(get_text("log_wolf_attack_home_fail"))
                return False
        else:
            self.logger.warning(get_text("log_wolf_attack_btn_missing"))
            return False

    # --- 辅助方法 ---

    def get_required_stamina(self, hero_config):
        """计算理论所需体力"""
        required = 25
        if "diana" in hero_config:
            diana_level = self.data.get_cfg("modules.general.diana_level", 0)
            if diana_level > 0:
                costs = self.DIANA_COST_TABLE.get(diana_level, self.DEFAULT_COST)
                required = costs[0]
        return required

    def get_actual_cost(self):
        """根据当前是否识别到 Diana 计算实际消耗"""
        # 注意：这里使用父类的方法检查屏幕上是否有 Diana 头像
        if self.find_diana():
            diana_level = self.data.get_cfg("modules.general.diana_level", 0)
            if diana_level > 0:
                return self.DIANA_COST_TABLE.get(diana_level, self.DEFAULT_COST)[0]
        return 25