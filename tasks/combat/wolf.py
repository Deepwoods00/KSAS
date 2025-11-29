from tasks.combat.combat_task import CombatTask
from i18n.i18n import get_text
from airtest.core.api import Template

class WolfTask(CombatTask):
    # UI 配置定义
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Wolf Task",
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
                {"value": "wait_1h", "label": "opt_fallback_wait"}
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
        # 获取配置
        # 注意：配置键名需要加上 modules.wolftask. 前缀
        use_one_soldier = self.data.get_cfg("modules.wolftask.one_soldier", False)
        hero_config = self.data.get_cfg("modules.wolftask.heroes", "none")
        fallback_policy = self.data.get_cfg("modules.wolftask.fallback_policy", "use_default")
        max_attacks = self.data.get_cfg("modules.wolftask.max_attacks", 10)
        
        # 检查次数限制
        # 注意：datastore.py 中定义的方法是 get_runtime(key, default)
        current_attacks = self.data.get_runtime("wolf.attack_count", 0)
        if current_attacks >= max_attacks:
            self.logger.info(get_text("log_wolf_finished"))
            # 自动禁用任务
            self.data.set_cfg("modules.wolftask.enable", False)
            return False

        self.logger.info(get_text("log_wolf_start", use_one_soldier, hero_config))

        # 0. 预检查 (Home Page, 空闲队列, 体力)
        if not self.pre_check(hero_config):
            return False

        # 1. 寻找 Wolf (Backpack -> Check -> Wolf -> Attack)
        if not self.find_and_click_wolf():
            self.logger.info(get_text("log_wolf_find_fail"))
            return False

        # 2. 战斗准备 (兵力 & 英雄)
        if not self.prepare_combat(use_one_soldier, hero_config, fallback_policy):
            return False

        # 3. 发起集结
        if self.start_rally():
            # 1. 更新出击计数 (减少剩余次数)
            # 注意：这里直接修改配置中的 max_attacks，从而同步到 UI
            new_max_attacks = max(0, max_attacks - 1)
            self.data.set_cfg("modules.wolftask.max_attacks", new_max_attacks)
            self.logger.info(get_text("log_wolf_attacks_left", new_max_attacks))
            
            # 如果剩余次数为0，自动禁用任务
            if new_max_attacks == 0:
                self.logger.info(get_text("log_wolf_finished"))
                self.data.set_cfg("modules.wolftask.enable", False)

            # 2. 扣除体力
            # 根据 Diana 技能等级计算消耗
            # 检查当前队列中是否有 Diana (使用父类 CombatTask 的 find_diana 方法)
            cost = 25 # 默认消耗
            if self.find_diana():
                # 获取 Diana 技能等级
                diana_level = self.data.get_cfg("modules.general.diana_level", 0)
                # 查表计算 (集结消耗)
                if diana_level > 0:
                    costs = self.DIANA_COST_TABLE.get(diana_level, self.DEFAULT_COST)
                    cost = costs[0] # 集结消耗是第一个值
                    self.logger.info(get_text("log_wolf_diana_found", diana_level, cost))
            else:
                self.logger.info(get_text("log_wolf_diana_not_found"))
            
            current_stamina = self.data.get_stat("stamina", 0)
            new_stamina = max(0, current_stamina - cost)
            self.data.set_stat("stamina", new_stamina)
            self.logger.info(get_text("log_wolf_deduct_stamina", cost, new_stamina))
            
            # 3. 减少空闲队列
            current_idle = self.sidebar.idle_march_count
            new_idle = max(0, current_idle - 1)
            self.data.set_stat("sidebar.idle_queues", new_idle)
            self.sidebar.idle_march_count = new_idle
            self.logger.info(get_text("log_wolf_deduct_queue", new_idle))
            
            return True
        
        return False

    def pre_check(self, hero_config):
        """
        0. 先确定在home page，确定有空闲队列，如果指定用戴安娜要确定体力>20，未指定英雄则确定体力>25
        """
        # 0.1 确保在 Home Page
        self.device.ensure_home()

        # 0.2 检查空闲队列
        idle_queues = self.sidebar.get_idle_march_queues()
        if idle_queues <= 0:
            self.logger.warning("没有空闲队列")
            return False

        # 0.3 检查体力
        # 根据 Diana 技能等级动态计算所需体力
        required_stamina = 25 # 默认消耗
        if "diana" in hero_config:
            diana_level = self.data.get_cfg("modules.general.diana_level", 0)
            if diana_level > 0:
                costs = self.DIANA_COST_TABLE.get(diana_level, self.DEFAULT_COST)
                required_stamina = costs[0] # 集结消耗
        
        # 获取当前体力 (从 DataStore 中读取)
        # 注意：这里读取的是缓存的体力值，需要确保有其他任务(如 update_stamina)定期更新它
        current_stamina = self.data.get_stat("stamina", 0)
        
        self.logger.info(get_text("log_wolf_stamina_check", current_stamina, required_stamina))

        if current_stamina <= required_stamina:
            self.logger.warning(get_text("log_wolf_stamina_low", current_stamina, required_stamina))
            return False
        
        return True

    def find_and_click_wolf(self):
        """
        1. 点击backpack.png
        2. 点击（630，120）
        3. 在屏幕上寻找check.png，如果成功则进行第四步，不成功则打断任务，返回错误。
        4. 查找并点击wolf.png
        5. 点击btn_blue.png，之后sleep（1）
        6. 点击（360，570）
        7. 点击btn_orange.png
        8. 点击btn_blue.png
        """
        IMG_BACKPACK = Template(r"assets/images/home/backpack.png", threshold=0.9)
        IMG_CHECK = Template(r"assets/images/wolf/check.png", threshold=0.9)
        IMG_WOLF = Template(r"assets/images/wolf/wolf.png", threshold=0.9)
        IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)
        IMG_BTN_ORANGE = Template(r"assets/images/btn/btn_orange.png", threshold=0.9)

        # 1. 点击 backpack.png
        self.logger.info("点击背包")
        if not self.device.click(IMG_BACKPACK):
            self.logger.warning("未找到背包按钮")
            return False
        self.device.sleep(1)

        # 2. 点击（630，120）
        self.logger.info("点击指定位置 (630, 120)")
        self.device.click((630, 120))
        self.device.sleep(1)

        # 3. 在屏幕上寻找 check.png
        self.logger.info("寻找 check.png")
        if not self.device.exists(IMG_CHECK):
            self.logger.warning("未找到 check.png，任务中断")
            return False
        
        # 4. 查找并点击 wolf.png
        self.logger.info("寻找并点击 wolf.png")
        if not self.device.click(IMG_WOLF):
            self.logger.warning("未找到 wolf.png")
            return False
        self.device.sleep(0.5)

        # 5. 点击 btn_blue.png，之后 sleep(1)
        self.logger.info("点击蓝色按钮 (使用)")
        if not self.device.click(IMG_BTN_BLUE):
            self.logger.warning("未找到蓝色按钮")
            return False
        self.device.sleep(1)

        # 6. 点击（360，570）
        self.logger.info("点击指定位置 (360, 570)")
        self.device.click((360, 570))
        self.device.sleep(0.5)

        # 7. 点击 btn_orange.png
        self.logger.info("点击橙色按钮 (搜索/确认)")
        if not self.device.click(IMG_BTN_ORANGE):
            self.logger.warning("未找到橙色按钮")
            return False
        self.device.sleep(1) # 等待地图跳转

        # 8. 点击 btn_blue.png (攻击/集结)
        self.logger.info("点击蓝色按钮 (攻击/集结)")
        # 这里可能需要等待一下，因为地图跳转和怪物显示需要时间
        self.device.sleep(1.5)
        if not self.device.click(IMG_BTN_BLUE):
            self.logger.warning("未找到蓝色按钮 (攻击/集结)")
            return False
        self.device.sleep(1)

        return True

    def prepare_combat(self, use_one_soldier, hero_config, fallback_policy):
        """
        战斗准备：设置兵力，选择英雄
        """
        # 验证是否在战斗页面 (实际逻辑中需要确保已进入)
        self.verify_combat_page()
        

        
        # 解析英雄列表
        target_heroes = []
        if hero_config == "diana":
            target_heroes = ["diana"]
        elif hero_config == "diana_fahd":
            target_heroes = ["diana", "fahd"]
            
        # 选择英雄
        if target_heroes:
            try:
                self.select_heroes(target_heroes)
            except Exception as e:
                if fallback_policy == "wait_1h":
                    self.logger.info(get_text("log_wolf_hero_fail_wait", e))
                    # 设置下次运行时间推迟1小时 (通过返回 False 或修改 interval，这里暂时返回 False 中断)
                    # 实际应用中可能需要更复杂的调度控制
                    return False
                else:
                    self.logger.info(get_text("log_wolf_hero_fail_default", e))
                    # 选将失败，可能停留在英雄选择界面，需要按 BACK 返回出击页面
                    self.device.keyevent("BACK")
                    self.device.sleep(0.5)
                    # 继续执行，不选将即为默认 (或者说不使用英雄)
        
        # 设置兵力
        if use_one_soldier:
            self.set_one_soldier(True)
        
        return True

    def start_rally(self):
        """
        点击集结按钮
        """
        # 1. 检查体力是否足够 (使用 check_stamina_sufficient 检测红色警示)
        # 注意：这里是在战斗配置页面进行的最后一次检查，防止体力突然不足
        if not self.check_stamina_sufficient():
            self.logger.warning(get_text("log_wolf_rally_stamina_low"))
            
            # 返回主页
            self.device.ensure_home()
            
            # 将任务注册到5分钟后进行
            self.set_next_run(seconds=300)
            return False

        # 2. 点击出击按钮
        # 暂时使用 btn_blue.png 作为出击按钮
        IMG_BTN_BLUE = Template(r"assets/images/btn/btn_blue.png", threshold=0.9)
        
        self.logger.info("点击出击/集结按钮")
        if self.device.click(IMG_BTN_BLUE):
            self.device.sleep(0.5)
            # 验证是否成功 (verify_attack_success)
            return self.verify_attack_success()
        else:
            self.logger.warning("未找到出击按钮")
            return False