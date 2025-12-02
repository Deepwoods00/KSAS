from tasks.base_task import BaseTask
from airtest.core.api import Template
from i18n.i18n import get_text
from basic import TaskInterruptedError
import cv2

class CombatTask(BaseTask):
    """
    战斗任务基类
    处理通用的编队、选将、调兵逻辑
    """

    # 戴安娜减耗表 (技能等级: (集结体力, 打野体力))
    DIANA_COST_TABLE = {
        1: (23, 9),
        2: (22, 9),
        3: (22, 9),
        4: (21, 9),
        5: (20, 8)
    }
    DEFAULT_COST = (25, 10)

    # 战斗配置页面按钮
    IMG_CLEAR_FULL = Template(r"assets/images/combat/clear_full.png", threshold=0.9)
    IMG_EQUAL = Template(r"assets/images/combat/equal.png", threshold=0.9)
    IMG_ADD = Template(r"assets/images/combat/add.png", threshold=0.9)

    # Stamina Update Templates
    IMG_INTEL = Template(r"assets/images/home/intel.png", threshold=0.9)
    IMG_BTN_GO_MAP = Template(r"assets/images/home/btn_go_map.png", threshold=0.9)

    def __init__(self, device, data):
        super().__init__(device, data)
        self.target_heroes = []
        self.soldier_count = 0
        
        # Number templates for stamina update
        self.number_templates = {}
        for i in range(10):
            self.number_templates[i] = Template(f"assets/images/number/{i}.png", threshold=0.9)

    def verify_combat_page(self):
        """
        确保在战斗配置页面
        """
        img_formation = Template(r"assets/images/combat/formation1.png", threshold=0.9)
        img_lock = Template(r"assets/images/combat/lock.png", threshold=0.9)
        
        if not (self.device.exists(img_formation) or self.device.exists(img_lock)):
            raise Exception(get_text("err_not_in_combat_page"))
        return True

    def calculate_cost(self, mode="rally"):
        skill_level = self.data.get_cfg("modules.general.diana_level", 0)
        if skill_level == 0:
            return self.DEFAULT_COST[0] if mode == "rally" else self.DEFAULT_COST[1]

        if self.find_diana():
            costs = self.DIANA_COST_TABLE.get(skill_level, self.DEFAULT_COST)
            cost = costs[0] if mode == "rally" else costs[1]
            self.logger.info(get_text("log_diana_cost", skill_level, cost))
            return cost
        else:
            cost = self.DEFAULT_COST[0] if mode == "rally" else self.DEFAULT_COST[1]
            self.logger.info(get_text("log_normal_cost", cost))
            return cost

    def find_diana(self):
        # 确保路径正确
        img_diana = Template(r"assets/images/heroes/diana_big.png", threshold=0.9)
        return self.device.exists(img_diana)

    def select_heroes(self, heroes: list):
        """
        根据传入的英雄列表进行选将
        :param heroes: list, 英雄名称列表 (e.g. ['diana', 'jessie'])
        """
        if not heroes:
            self.logger.info(get_text("log_no_hero_specified"))
            return

        # 0. 检测是否存在 add.png
        if not self.device.exists(self.IMG_ADD):
            self.logger.info(get_text("log_clearing_heroes"))
            # 1. 点击清除按钮 (237, 260)
            self.device.click((237, 260))
            self.device.sleep(2.5)
            
            # 1.1 再次确认 add.png
            # 注意：exists 方法内部会调用 _find_template_pos，它会重新截图
            if not self.device.exists(self.IMG_ADD):
                self.logger.warning(get_text("log_clear_hero_failed"))
        
        # 2. 点击第一个英雄栏 (174, 374)
        self.logger.info(get_text("log_click_first_hero_slot"))
        self.device.click((174, 374))
        self.device.sleep(1) # 等待英雄选择界面加载

        # 3. 循环选择英雄
        for i, hero_name in enumerate(heroes):
            self.logger.info(get_text("log_searching_hero", hero_name, i+1, len(heroes)))
            
            # 构建小头像 Template
            img_hero_small = Template(f"assets/images/heroes/{hero_name}_small.png", threshold=0.85)
            
            found = False
            # 尝试寻找 (最多拖动3次)
            for attempt in range(4): # 0 (初始) + 3 (拖动)
                if self.device.exists(img_hero_small):
                    self.logger.info(get_text("log_hero_found", hero_name))
                    self.device.click(img_hero_small)
                    self.device.sleep(0.5)
                    found = True
                    break
                
                if attempt < 3:
                    self.logger.info(get_text("log_hero_not_found_scroll", hero_name, attempt+1))
                    # 起始点 (358, 905) -> 终止点 (358, 608)
                    self.device.swipe((358, 905), (358, 608), duration=1.5)
                    self.device.sleep(1) # 等待滚动停止
            
            if not found:
                raise Exception(f"无法找到目标英雄: {hero_name}")

            # 找到并点击后，点击确认按钮 (440, 1000)
            self.logger.info(get_text("log_click_confirm"))
            self.device.click((440, 1000))
            self.device.sleep(0.5) # 等待跳转到下一个位置或返回
            
            # 注意：根据描述，按下确认后会自动跳转到下一个英雄选择页面
            # 所以不需要手动点击下一个栏位，除非是最后一个英雄选完后需要返回

        # 4. 英雄选择完毕后按一次 back 按键返回出击页面
        # 如果选完最后一个英雄，界面可能还在英雄选择页(如果还有空位)，或者自动返回了？
        # 根据描述 "英雄选择完毕后按一次back按键返回出击页面"，假设需要手动返回
        self.logger.info(get_text("log_hero_selection_done"))
        self.device.keyevent("BACK")
        self.device.sleep(0.5)

    def set_one_soldier(self, enable=True):
        """
        设置是否以1兵出击
        :param enable: bool, True=1兵, False=平均分配
        """
        # 1兵选项坐标 (这个还是保留坐标，因为可能是弹窗里的选项)
        BTN_ONE_SOLDIER = (658, 690)
        
        if enable:
            self.logger.info(get_text("log_set_one_soldier"))
            # 点击清除/满兵按钮 (打开设置菜单)
            self.device.click(self.IMG_CLEAR_FULL)
            self.device.sleep(0.2)
            # 点击1兵选项
            self.device.click(BTN_ONE_SOLDIER)
            self.device.sleep(0.2)
        else:
            self.logger.info(get_text("log_set_avg_soldier"))
            # 点击平均分配按钮
            self.device.click(self.IMG_EQUAL)
            self.device.sleep(0.2)

    def verify_attack_success(self):
        """
        验证出击是否成功
        判断屏幕上是否同时有：home_check.png 和 btn_town.png
        :return: bool
        """
        # img_home_check = Template(r"assets/images/home/home_check.png", threshold=0.9)
        img_home_check = self.device.IMG_HOME_CHECK
        img_btn_town = Template(r"assets/images/home/btn_town.png", threshold=0.9)
        
        # 等待一小段时间让界面切换
        self.device.sleep(1)
        
        if self.device.exists(img_home_check) and self.device.exists(img_btn_town):
            self.logger.info(get_text("log_attack_success"))
            return True
        else:
            self.logger.warning(get_text("log_attack_failed"))
            return False

    def check_stamina_sufficient(self, cost):
        """
        检查体力是否足够 (基于缓存 + Double Check)
        
        :param cost: int, 需要消耗的体力值
        :return:
            - True: 体力充足，可以直接继续
            - "RESTART": 体力充足，但因为执行了回城更新，需要任务层重启流程
            - int: 体力不足，返回缺少的体力值 (missing_stamina)
        """
        # 1. Check Cached Stamina
        current_stamina = self.data.get_stat("stamina", 0)
        
        if current_stamina >= cost:
            self.logger.info(get_text("log_stamina_sufficient_cached", current_stamina, cost))
            return True
            
        # 2. Double Check (Go Home -> Update -> Check Again)
        self.logger.warning(get_text("log_stamina_low_cached", current_stamina, cost))
        self.logger.info(get_text("log_trigger_stamina_update"))
        
        self.device.ensure_home()
        self.update_stamina()
        
        new_stamina = self.data.get_stat("stamina", 0)
        
        if new_stamina >= cost:
            self.logger.info(get_text("log_stamina_sufficient_updated", new_stamina, cost))
            return "RESTART"
        else:
            missing = cost - new_stamina
            self.logger.warning(get_text("log_stamina_insufficient_final", new_stamina, cost, missing))
            return missing

    def detect_current_heroes(self):
        """
        检测当前页面显示的英雄
        :return: list, 英雄名称列表 (e.g. ['diana', 'jessie'])
        """
        import os
        
        detected_heroes = []
        heroes_dir = "assets/images/heroes"
        
        if not os.path.exists(heroes_dir):
            self.logger.warning(get_text("log_hero_dir_missing", heroes_dir))
            return []
            
        # 遍历目录下的所有文件
        for filename in os.listdir(heroes_dir):
            if filename.endswith("_big.png"):
                # 提取英雄名称 (去掉 _big.png)
                hero_name = filename.replace("_big.png", "")
                
                # 构建 Template
                img_path = os.path.join(heroes_dir, filename)
                tpl = Template(img_path, threshold=0.9)
                
                # 检测是否存在
                if self.device.exists(tpl):
                    self.logger.info(get_text("log_hero_detected", hero_name))
                    detected_heroes.append(hero_name)
                    
        return detected_heroes

    def update_stamina(self):
        """
        执行体力更新逻辑
        """
        retry_count = 0
        max_retries = 1
        
        while retry_count <= max_retries:
            # Step 0: Ensure Home
            self.device.ensure_home()

            # Step 0.5: Check for btn_go_map
            if self.device.exists(self.IMG_BTN_GO_MAP):
                self.logger.info(get_text("log_found_go_map"))
                self.device.click(self.IMG_BTN_GO_MAP)
                self.device.sleep(1.0)
            
            # Step 0_Click: Click Intel
            if self.device.exists(self.IMG_INTEL):
                self.device.click(self.IMG_INTEL)
            else:
                self.logger.warning(get_text("log_intel_icon_missing"))
                retry_count += 1
                continue
                
            # Wait 0.8s
            self.device.sleep(0.8)
            
            # Step 1: Snapshot and Crop
            # Area: 600, 25, 660, 53
            screen_path = self.device.snapshot()
            if not screen_path:
                self.logger.error(get_text("log_snapshot_failed"))
                retry_count += 1
                continue
                
            img = cv2.imread(screen_path)
            if img is None:
                self.logger.error(get_text("log_read_snapshot_failed"))
                retry_count += 1
                continue
                
            # Crop: y1:y2, x1:x2
            # Area from MD: 600, 25, 660, 53 (x1, y1, x2, y2)
            # OpenCV uses img[y:h, x:w]
            x1, y1, x2, y2 = 600, 25, 660, 53
            crop_img = img[y1:y2, x1:x2]
            
            # Step 2: Match Numbers
            results = [] # List of (x_coord, digit)
            
            # Loop 0-9
            for digit in range(10):
                template = self.number_templates[digit]
                # match_all_in returns list of results
                matches = template.match_all_in(crop_img)
                
                if matches:
                    for match in matches:
                        # match is usually a dict with 'result' (center point)
                        if isinstance(match, dict) and 'result' in match:
                            x = match['result'][0]
                            results.append((x, digit))
                        elif isinstance(match, (tuple, list)):
                                x = match[0]
                                results.append((x, digit))
                
                # Check Limit
                if len(results) >= 3:
                    break
            
            # Check Empty
            if not results:
                self.logger.warning(get_text("log_stamina_ocr_failed", retry_count, max_retries))
                retry_count += 1
                continue
            
            # Sort by X coordinate
            results.sort(key=lambda x: x[0])
            
            # Concat
            stamina_str = "".join([str(r[1]) for r in results])
            try:
                stamina_val = int(stamina_str)
            except ValueError:
                self.logger.error(get_text("log_stamina_parse_failed", stamina_str))
                retry_count += 1
                continue
                
            # Save
            self.logger.info(get_text("log_stamina_updated", stamina_val))
            self.data.set_stat("stamina", stamina_val)
            
            # Return to home to be safe (optional, but good practice if we left it in Intel screen)
            self.device.ensure_home()
            
            # End
            return True
            
        self.logger.error(get_text("log_stamina_update_failed_final"))
        self.device.ensure_home()
        return False