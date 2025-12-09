import time
import cv2
from airtest.core.api import Template
from game.sidebar import Sidebar
from i18n.i18n import get_text

class TroopType:
    INFANTRY = "infantry" # 对应 barracks
    CAVALRY = "cavalry"   # 对应 stable (骑兵)
    ARCHER = "archer"     # 对应 range (弓兵)

class TrainMode:
    TRAIN = "train"      # 新兵
    PROMOTE = "promote"  # 晋升

class TroopManager:
    def __init__(self, device, data):
        self.device = device
        self.data = data
        self.logger = self.device.logger
        self.sidebar = Sidebar(device, data)

        # ==========================================
        # 1. 侧边栏锚点与状态资源 (Sidebar Assets)
        # ==========================================
        self.anchors = {
            TroopType.INFANTRY: Template(r"assets/images/sidebar/inf.png", threshold=0.9),
            TroopType.CAVALRY:  Template(r"assets/images/sidebar/cav.png", threshold=0.9),
            TroopType.ARCHER:   Template(r"assets/images/sidebar/arc.png", threshold=0.9)
        }
        
        # 状态信号
        # go.png: 空闲 (需开启 RGB 区分灰色状态)
        self.IMG_STATUS_GO = Template(r"assets/images/sidebar/go.png", threshold=0.94, rgb=True)
        # troop_done.png: 训练完成 (待领取)
        self.IMG_STATUS_DONE = Template(r"assets/images/sidebar/troop_done.png", threshold=0.9)

        # ==========================================
        # 2. 入口与导航资源 (Entry)
        # ==========================================
        self.IMG_BTN_TRAIN_ENTRY = Template(r"assets/images/troop/train.png", threshold=0.9)
        
        # ==========================================
        # 3. 内部状态验证资源 (Inside State)
        # ==========================================
        self.IMG_STATE_PLUS = Template(r"assets/images/troop/plus.png", threshold=0.9) 
        self.IMG_STATE_STOP = Template(r"assets/images/troop/stop.png", threshold=0.9)
        
        # ==========================================
        # 4. 功能按钮 (Buttons)
        # ==========================================
        # 蓝色训练按钮 (通常用于训练新兵)
        self.IMG_BTN_BLUE_TRAIN = Template(r"assets/images/troop/btn_blue_train.png", threshold=0.9, rgb=True)
        # 蓝色晋升按钮 (通常用于晋升确认)
        self.IMG_BTN_BLUE_PROMO = Template(r"assets/images/troop/btn_blue_promo.png", threshold=0.9, rgb=True)
        # 黄色按钮 (可能用于加速或金币训练?)
        self.IMG_BTN_YELLOW = Template(r"assets/images/troop/btn_yellow.png", threshold=0.9, rgb=True)
        # 晋升切换图标 (向上箭头)
        self.IMG_ICON_PROMOTE = Template(r"assets/images/troop/promote.png", threshold=0.9, rgb=True)

        # ==========================================
        # 5. 页签状态图标 (Tabs)
        # ==========================================
        # 激活状态 (用来判断当前在哪)
        self.tabs_on = {
            TroopType.INFANTRY: Template(r"assets/images/troop/barracks_on.png", threshold=0.9, rgb=True),
            TroopType.CAVALRY:  Template(r"assets/images/troop/stable_on.png", threshold=0.9, rgb=True),
            TroopType.ARCHER:   Template(r"assets/images/troop/range_on.png", threshold=0.9, rgb=True)
        }
        
        # 未激活状态 (用来点击切换)
        self.tabs_off = {
            TroopType.INFANTRY: Template(r"assets/images/troop/barracks_off.png", threshold=0.9, rgb=True),
            TroopType.CAVALRY:  Template(r"assets/images/troop/stable_off.png", threshold=0.9, rgb=True),
            TroopType.ARCHER:   Template(r"assets/images/troop/range_off.png", threshold=0.9, rgb=True)
        }

        # ==========================================
        # 6. 等级图标 (1-10) & 常量
        # ==========================================
        self.tier_icons = {}
        for i in range(1, 11): 
            self.tier_icons[i] = Template(f"assets/images/troop/{i}.png", threshold=0.885)

        # 滑动坐标 (根据需求定点滑动)
        self.POS_SCROLL_LEFT = (10, 700)
        self.POS_SCROLL_RIGHT = (706, 710)

    # ==========================================
    # [功能] 兵营状态扫描 (高效)
    # ==========================================
    def scan_building_states(self):
        """
        一次截图，批量判断三个兵营的状态。
        返回: dict { 'infantry': True/False/None, ... }
        - True: Idle (Go or Done) -> 可操作
        - False: Busy (Nothing found) -> 忙碌中
        - None: Unknown (Anchor not found) -> 未解锁或需滑动
        """
        self.logger.info("Scanning troop building states...")
        results = {}
        
        # 1. 确保在事务页
        if not self.sidebar.switch_to_affairs_page():
            self.logger.error("Failed to open sidebar for scanning.")
            return {}

        # 2. 截取一次全屏快照
        screen_path = self.device.snapshot()
        if not screen_path:
            return {}
        
        screen = cv2.imread(screen_path)
        if screen is None:
            return {}

        # 3. 遍历三个兵种
        # 搜索区域 X 范围 (参考 sidebar.py 的 find_in_anchor_row)
        CROP_X_MIN, CROP_X_MAX = 373, 434
        Y_PADDING = 15

        for t_type, anchor_tpl in self.anchors.items():
            # A. 在快照中寻找锚点
            anchor_res = anchor_tpl.match_in(screen)
            
            if not anchor_res:
                results[t_type] = None # Unknown
                continue

            try:
                # B. 计算裁剪区域 (兼容 dict 或 tuple 返回值)
                if isinstance(anchor_res, dict):
                    rect = anchor_res.get('rectangle')
                    if rect:
                        y_top = int(rect[0][1])
                        y_bottom = int(rect[2][1])
                    else:
                        cx, cy = anchor_res['result']
                        h, w = anchor_tpl._imread().shape[:2]
                        y_top = int(cy - h/2)
                        y_bottom = int(cy + h/2)
                else:
                    # tuple
                    cx, cy = anchor_res
                    h, w = anchor_tpl._imread().shape[:2]
                    y_top = int(cy - h/2)
                    y_bottom = int(cy + h/2)

                # 应用边界检查
                y_min = max(0, y_top - Y_PADDING)
                y_max = min(screen.shape[0], y_bottom + Y_PADDING)
                
                # C. 裁剪出该行右侧区域
                cropped_img = screen[y_min:y_max, CROP_X_MIN:CROP_X_MAX]
                
                # D. 在小图里搜索状态信号
                is_idle = False
                
                # 检查1: 是否有 Done (训练完成)
                if self.IMG_STATUS_DONE.match_in(cropped_img):
                    is_idle = True
                
                # 检查2: 是否有 Go (空闲)
                elif self.IMG_STATUS_GO.match_in(cropped_img):
                    is_idle = True
                
                # E. 记录结果
                # True = Idle (可练), False = Busy (倒计时)
                results[t_type] = is_idle
                
            except Exception as e:
                self.logger.error(f"Error scanning {t_type}: {e}")
                results[t_type] = None

        self.logger.info(f"Scan results: {results}")
        return results

    # ==========================================
    # 核心动作 (Atomic Actions)
    # ==========================================

    def enter_barracks(self):
        """[动作] 进入兵营"""
        self.logger.info(get_text("log_troop_enter_start"))

        if not self.sidebar.switch_to_affairs_page():
            self.logger.error(get_text("err_troop_sidebar_fail"))
            return False

        # 使用 self.anchors 中的步兵图标
        pos_inf = self.device.exists(self.anchors[TroopType.INFANTRY])
        if not pos_inf:
            self.logger.error(get_text("err_troop_icon_missing"))
            return False
            
        self.logger.info(get_text("log_troop_click_inf"))
        self.device.click(pos_inf)
        self.device.sleep(1.5)

        target_pos = (352, 580)
        for _ in range(3):
            self.device.click(target_pos)
            time.sleep(0.4)
            
        pos_train = self.device.exists(self.IMG_BTN_TRAIN_ENTRY)
        if not pos_train:
            self.logger.error(get_text("err_troop_bubble_missing"))
            return False
            
        self.logger.info(get_text("log_troop_click_train"))
        self.device.click(pos_train)
        self.device.sleep(1.0) 

        # 验证进入
        if self.check_state() != "unknown":
            self.logger.info(get_text("log_troop_enter_success"))
            return True
        else:
            self.logger.error(get_text("err_troop_enter_valid_fail"))
            return False

    def check_state(self):
        """[状态检测]"""
        if self.device.exists(self.IMG_STATE_PLUS):
            return "idle"
        if self.device.exists(self.IMG_STATE_STOP):
            return "busy"
        return "unknown"

    def get_current_tab(self):
        """获取当前所在的兵营页面类型"""
        for t_type, tpl in self.tabs_on.items():
            if self.device.exists(tpl):
                return t_type
        return None

    def switch_to_tab(self, target_type):
        """[动作] 切换到指定兵营页签"""
        self.logger.info(get_text("log_troop_switch_tab", target_type))
        current = self.get_current_tab()
        
        # 1. 已经在目标页签
        if current == target_type:
            return True
            
        # 2. 无页签显示 (小号模式)
        if current is None:
            if target_type == TroopType.INFANTRY:
                self.logger.info(get_text("log_troop_no_tab_default"))
                return True
            else:
                self.logger.warning(get_text("warn_troop_tab_locked", target_type))
                return False

        # 3. 有页签，执行切换
        target_off_tpl = self.tabs_off.get(target_type)
        if not target_off_tpl:
            self.logger.error(get_text("err_troop_asset_missing", target_type))
            return False
            
        if self.device.click(target_off_tpl):
            self.device.sleep(1.0) # 等待切换
            
            # 验证
            if self.device.exists(self.tabs_on[target_type]):
                self.logger.info(get_text("log_troop_switch_success", target_type))
                return True
            else:
                self.logger.warning(get_text("warn_troop_switch_fail", target_type))
                return False
        
        self.logger.warning(get_text("warn_troop_tab_not_found", target_type))
        return False

    def select_tier(self, level):
        """
        [动作] 选择兵种等级
        逻辑: 尝试直接找 -> 根据范围滑动 -> 再次找
        """
        target_tpl = self.tier_icons.get(level)
        if not target_tpl:
            self.logger.error(f"Asset missing for Tier {level}")
            return False

        self.logger.info(get_text("log_troop_select_tier", level))

        # 1. 第一次寻找
        if self.device.exists(target_tpl):
            self.logger.info(f"Tier {level} found directly.")
            self.device.click(target_tpl)
            self.device.sleep(0.5)
            return True
        
        # 2. 没找到，执行定点滑动
        if 1 <= level <= 5:
            self.logger.info(get_text("log_troop_scroll_low")) 
            self.device.drag_and_hold(self.POS_SCROLL_LEFT, self.POS_SCROLL_RIGHT, duration=1.0, hold=1.0)
        
        elif 6 <= level <= 10:
            self.logger.info(get_text("log_troop_scroll_high")) 
            self.device.drag_and_hold(self.POS_SCROLL_RIGHT, self.POS_SCROLL_LEFT, duration=1.0, hold=1.0)
        
        else:
            self.logger.warning(f"Level {level} out of range (1-10).")
            return False

        # 3. 滑动后再次寻找
        self.device.sleep(0.8)
        if self.device.exists(target_tpl):
            self.logger.info(f"Tier {level} found after scrolling.")
            self.device.click(target_tpl)
            self.device.sleep(0.8)
            return True
        
        self.logger.error(get_text("err_troop_tier_not_found", level))
        return False

    def execute_train_action(self):
        """[动作] 执行训练新兵"""
        self.logger.info(get_text("log_troop_action_train"))
        
        train_btn = self.device.exists(self.IMG_BTN_BLUE_TRAIN)
        if train_btn:
            self.device.click(train_btn)
            self.device.sleep(1.0) # 改为1s
        else:
            self.logger.error(get_text("err_troop_train_btn_missing"))
            return False

        # 验证结果 (检查 Stop 图标)
        if self.device.exists(self.IMG_STATE_STOP):
            self.logger.info(get_text("log_troop_train_success"))
            return True
        else:
            self.logger.warning(get_text("err_troop_train_verify_fail"))
            return False

    def execute_promote_action(self):
        """
        [动作] 执行晋升流程
        返回: True (成功) / False (失败) / "NO_PROMOTABLE" (无兵可升)
        """
        self.logger.info(get_text("log_troop_action_promote"))
        
        # 1. 检查箭头
        arrow_pos = self.device.exists(self.IMG_ICON_PROMOTE)
        if not arrow_pos:
            self.logger.info(get_text("log_troop_no_promotable"))
            return "NO_PROMOTABLE"
            
        # 2. 点击箭头
        self.device.click(arrow_pos)
        self.device.sleep(0.8) 
            
        # 3. 点击晋升确认
        promo_btn = self.device.exists(self.IMG_BTN_BLUE_PROMO)
        if promo_btn:
            self.device.click(promo_btn)
            self.device.sleep(1.0) # 改为1s
        else:
            self.logger.error(get_text("err_troop_promote_btn_missing"))
            return False

        # 4. 验证 (检查 Stop)
        if self.device.exists(self.IMG_STATE_STOP):
            self.logger.info(get_text("log_troop_promote_success"))
            return True
        else:
            self.logger.warning(get_text("err_troop_promote_verify_fail"))
            return False

    def exit_barracks(self):
        """[动作] 退出界面"""
        self.device.keyevent("BACK")
        self.device.sleep(1.0)