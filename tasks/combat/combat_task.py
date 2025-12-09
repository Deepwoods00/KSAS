from tasks.base_task import BaseTask
from airtest.core.api import Template
from i18n.i18n import get_text
from basic import TaskInterruptedError
import cv2
from datetime import datetime, timezone, timedelta
import math

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

    def get_disposable_stamina(self, current_stamina):
        """
        计算可用于普通战斗的'闲钱'体力。
        逻辑：在 Intel 任务刷新前 30 分钟内，强制锁住 75 点体力。
        """
        now = datetime.now(timezone.utc)
        
        # 1. 定义锁定窗口 (UTC)
        # Intel 刷新时间: 00:00, 08:00, 16:00
        # 锁定时间段: 23:30-00:00, 07:30-08:00, 15:30-16:00
        
        current_hour = now.hour
        current_minute = now.minute
        
        is_locked = False
        
        # 检查是否处于刷新前30分钟
        if (current_hour == 7 and current_minute >= 30) or \
           (current_hour == 15 and current_minute >= 30) or \
           (current_hour == 23 and current_minute >= 30):
            is_locked = True
            
        if is_locked:
            # 处于锁定窗口，必须保留 75 点
            reserved = 75
            disposable = max(0, current_stamina - reserved)
            
            if disposable < current_stamina:
                # 只有当体力确实被扣减了才打印日志，防止刷屏
                self.logger.info(get_text("log_stamina_locked_for_intel", reserved, disposable))
            
            return disposable
        
        # 平时：所有体力都可用
        return current_stamina

    

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
    
    def get_realtime_cost(self, mode="wild"):
        """
        [新增] 实时计算当前屏幕上的体力消耗
        :param mode: "wild" (野怪) 或 "rally" (集结)
        :return: int (消耗值)
        """
        diana_skill_lv = self.data.get_cfg("modules.general.diana_level", 0)
        
        # 默认消耗
        base_cost = 25 if mode == "rally" else 10
        
        # 如果戴安娜技能为0，无论她在不在场，消耗都不变
        if diana_skill_lv == 0:
            return base_cost

        # 检测屏幕上是否有戴安娜
        if self.find_diana():
            # 查表获取减免后的消耗
            costs = self.DIANA_COST_TABLE.get(diana_skill_lv, (25, 10))
            real_cost = costs[0] if mode == "rally" else costs[1]
            self.logger.info(get_text("log_diana_detected_cost", real_cost))
            return real_cost
        
        return base_cost

    def select_heroes(self, heroes: list):
        """
        [修复版] 英雄选择逻辑
        修复问题：找到头像后未点击确认按钮
        逻辑：
        1. 尝试清空并打开列表。
        2. 遍历英雄列表。
        3. 尝试在当前屏、回顶后、或滑动中寻找。
        4. 【关键】只要找到了，先点头像，立刻点确认按钮。
        5. 没找到则跳过。
        6. 最后智能退出。
        """
        if not heroes:
            self.logger.info(get_text("log_no_hero_specified"))
            return

        # ==========================================
        # 0. 初始化：清空并打开列表
        # ==========================================
        if not self.device.exists(self.IMG_ADD):
            self.logger.info(get_text("log_clearing_heroes"))
            self.device.click((237, 260)) # 点击清除
            self.device.sleep(2.0)
        
        self.logger.info(get_text("log_click_first_hero_slot"))
        self.device.click((174, 374)) # 打开列表
        self.device.sleep(1.5)

        # ==========================================
        # 1. 遍历目标列表
        # ==========================================
        found_count = 0
        
        for i, hero_name in enumerate(heroes):
            self.logger.info(f"Targeting hero: {hero_name} ({i+1}/{len(heroes)})")
            
            img_hero_small = Template(f"assets/images/heroes/{hero_name}_small.png", threshold=0.85)
            is_found_and_clicked = False # 标记本轮是否成功点到了头像
            
            # --- 步骤 A: 当前屏幕直接寻找 ---
            if self.device.exists(img_hero_small):
                self.logger.info(get_text("log_hero_found", hero_name))
                self.device.click(img_hero_small)
                self.device.sleep(0.5)
                is_found_and_clicked = True
            
            # --- 步骤 B: 回顶重置 (如果步骤A没找到，且是第2个英雄) ---
            elif i > 0:
                self.logger.info("Reseting list to top...")
                for _ in range(3):
                    self.device.swipe((351, 600), (351, 1213), duration=0.5)
                    self.device.sleep(0.2)
                self.device.sleep(1.0)
                
                if self.device.exists(img_hero_small):
                    self.logger.info(get_text("log_hero_found", hero_name))
                    self.device.click(img_hero_small)
                    self.device.sleep(0.5)
                    is_found_and_clicked = True

            # --- 步骤 C: 下滑寻找 (如果前两步都没找到) ---
            if not is_found_and_clicked:
                # self.logger.info(f"Scrolling to find {hero_name}...")
                for attempt in range(3):
                    self.device.drag_and_hold((349, 854), (357, 564), duration=1.0, hold=1.0)
                    
                    if self.device.exists(img_hero_small):
                        self.logger.info(get_text("log_hero_found", hero_name))
                        self.device.click(img_hero_small)
                        self.device.sleep(0.5)
                        is_found_and_clicked = True
                        break

            # --- [核心修复] 步骤 D: 确认选择 ---
            if is_found_and_clicked:
                self.logger.info("Clicking Confirm/Assign button...")
                self.device.click((440, 1000)) # 点击确认
                self.device.sleep(1.0)         # 等待窗口反应
                found_count += 1
            else:
                self.logger.warning(f"Hero {hero_name} unavailable. Skipping.")

        # ==========================================
        # 2. 结束：智能退出
        # ==========================================
        self.logger.info(f"Hero selection complete. Picked {found_count}/{len(heroes)}.")
        
        # 检查是否还在列表里 (如果没有均兵按钮，说明还在列表，需要补 BACK)
        if not self.device.exists(self.IMG_EQUAL):
            self.logger.info("Still in list view, pressing BACK.")
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
    
