# -*- coding: utf-8 -*-
import os
import time
import logging
import random
import threading
import cv2
import numpy as np
from functools import wraps
from datetime import datetime

# Airtest 核心类
from airtest.core.api import Template, wait, sleep
from airtest.core.android.android import Android
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import G
# 👇 【新增】引入这个常量，为了拿我们在 KSAS.py 里设置好的路径
from airtest.core.android import constant
from tools.resource_loader import ResourceLoader

class TaskInterruptedError(Exception):
    """任务被用户强制中断"""
    pass

# ==========================================
# 🛠️ 实例操作器
# ==========================================
class DeviceOperator:
    def __init__(self, serial, instance_id, data_dir_root="data", interrupt_callback=None):
        self.serial = serial
        self.instance_id = instance_id
        self.logger = logging.getLogger(f"{instance_id}.Device")
        
        self.base_dir = os.path.join(data_dir_root, instance_id)
        self.snapshot_dir = os.path.join(self.base_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

        # 🔒 实例级锁
        self.lock = threading.RLock()
        
        # ⏹️ 中断检查回调 (如果返回 True，说明需要立即停止)
        self.interrupt_callback = interrupt_callback

        self.adb = None
        self._is_connected = False

        # 👇 【新增 2】 加载核心安全资源 (替换 "123456" 为你在 KeyAuth 后台的真实 File ID)
        # 这张图就是 home_check.png
        self.IMG_HOME_CHECK = ResourceLoader().get_template("209805", threshold=0.9)

        # 如果下载失败，给个警告（或者直接抛异常）
        if self.IMG_HOME_CHECK is None:
            self.logger.error("⚠️ 核心安全资源加载失败！脚本可能无法判断主城状态。")

    # ==========================================
    # 🛡️ 装饰器
    # ==========================================
    def _safe_wrap(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            action_name = func.__name__
            with self.lock:
                # 1. 动作前检查中断
                self.check_interrupt()

                if not self._is_connected or not self.adb:
                    self.connect()

                try:
                    result = func(self, *args, **kwargs)
                    return True if result is None else result
                except TaskInterruptedError:
                    # 中断信号直接往上抛，给 Scheduler 捕获
                    raise
                except TargetNotFoundError:
                    self.logger.warning(f"[{action_name}] 未找到目标")
                    self._save_snapshot(f"{action_name}_404")
                    return False
                except Exception as e:
                    self.logger.error(f"[{action_name}] 异常: {e}")
                    self._save_snapshot(f"{action_name}_error")
                    return False
        return wrapper

    # ==========================================
    # 🔌 系统连接
    # ==========================================
    def check_interrupt(self):
        """检查是否应该立即停止"""
        if self.interrupt_callback and self.interrupt_callback():
            self.logger.warning(f"检测到中断信号 (Callback returned True)，强制停止操作！")
            raise TaskInterruptedError("Task interrupted by user")

    def connect(self):
        with self.lock:
            try:
                # 👇 【核心修改】这里不再只传 serial，而是把 adb_path 塞进去！
                # 这样 Airtest 就绝对不敢用别人的 ADB 了
                self.adb = Android(self.serial, adb_path=constant.ADB_PATH)
                
                self._is_connected = True
                self.logger.info(f"设备对象已挂载: {self.serial}")
                return True
            except Exception as e:
                self.logger.error(f"设备挂载失败: {e}")
                self._is_connected = False
                return False

    def _save_snapshot(self, tag):
        try:
            if not self.adb: return None
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{timestamp}_{tag}.png"
            filepath = os.path.join(self.snapshot_dir, filename)
            self.adb.snapshot(filename=filepath)
            return filepath
        except:
            return None

    def snapshot(self):
        """
        兼容性方法：返回截图路径
        """
        return self._save_snapshot("temp")

    # ==========================================
    # 🔍 内部辅助：图片匹配
    # ==========================================
    def _find_template_pos(self, target):
        """
        手动实现图片匹配，兼容多种返回格式
        """
        try:
            # 1. 截取当前屏幕
            temp_path = os.path.join(self.snapshot_dir, "tmp_match.png")
            self.adb.snapshot(filename=temp_path)
            
            # 2. 读取图片
            screen = cv2.imread(temp_path)
            if screen is None: return None

            # 3. 匹配
            res = target.match_in(screen)
            
            # 4. 【核心修复】兼容性处理
            if res:
                # 情况 A: 如果是字典 (Airtest 标准返回)，取 result 字段
                if isinstance(res, dict):
                    return res.get('result')
                # 情况 B: 如果直接是元组/列表 (坐标)，直接返回
                elif isinstance(res, (tuple, list)):
                    return res
                # 情况 C: 其他奇怪的对象，尝试直接用
                else:
                    return res
            
            return None
        except Exception as e:
            # 这里打印详细一点，方便调试
            self.logger.error(f"图片匹配异常: {e} (Type: {type(res) if 'res' in locals() else 'Unknown'})")
            return None

    # ==========================================
    # 👆 动作执行
    # ==========================================
    @_safe_wrap
    def click(self, target, times=1, offset=(0, 0)):
        pos = target
        if isinstance(target, Template):
            found = False
            for _ in range(3):
                self.check_interrupt() # 每次重试前都检查
                pos = self._find_template_pos(target)
                if pos:
                    found = True
                    break
                time.sleep(0.5)
            
            if not found:
                raise TargetNotFoundError("Template not found")
        
        for _ in range(times):
            self.check_interrupt() # 连点之间检查
            if pos:
                self.adb.touch(pos)
            if times > 1:
                time.sleep(random.uniform(0.2, 0.5))

    @_safe_wrap
    def swipe(self, start, end, duration=0.5):
        """
        基础滑动方法 (兼容 Airtest swipe)
        :param start: (x, y) 起点
        :param end: (x, y) 终点
        :param duration: 滑动耗时
        """
        self.adb.swipe(start, end, duration=duration)
        sleep(0.5)

    @_safe_wrap
    def swipe_screen(self, direction="up", scale=0.6, area=None):
        try:
            disp = self.adb.get_display_info()
            w, h = disp['width'], disp['height']
        except:
            w, h = 720, 1280

        if area:
            x1, y1, x2, y2 = map(int, area)
            bw, bh = x2 - x1, y2 - y1
            base_x, base_y = x1, y1
        else:
            bw, bh = w, h
            base_x, base_y = 0, 0

        cx, cy = base_x + bw * 0.5, base_y + bh * 0.5
        delta_h, delta_w = bh * scale * 0.5, bw * scale * 0.5

        if direction == "up":    start, end = (cx, cy + delta_h), (cx, cy - delta_h)
        elif direction == "down": start, end = (cx, cy - delta_h), (cx, cy + delta_h)
        elif direction == "left": start, end = (cx + delta_w, cy), (cx - delta_w, cy)
        elif direction == "right": start, end = (cx - delta_w, cy), (cx + delta_w, cy)
        else: return False

        self.adb.swipe(start, end) 
        sleep(0.8)

    @_safe_wrap
    def swipe_until_found(self, target, direction="up", scale=0.5, area=None, max_retry=5):
        for i in range(max_retry):
            self.check_interrupt() # 滑动前检查
            if self._exists_internal(target):
                return True
            self.logger.info(f"寻找目标... 滑动 #{i+1}")
            self.swipe_screen(direction=direction, scale=scale, area=area)
            time.sleep(0.5)
        return False

    @_safe_wrap
    def pinch(self, mode="in"):
        self.logger.warning("Pinch 动作在独立模式下暂不可用")
        pass

    @_safe_wrap
    def input_text(self, content, confirm=True):
        self.adb.text(str(content), enter=confirm)
        sleep(1)

    @_safe_wrap
    def keyevent(self, keyname):
        """
        模拟按键事件
        :param keyname: 键名 (e.g. "BACK", "HOME")
        """
        self.adb.keyevent(keyname)
        sleep(0.5)

    @_safe_wrap
    def press_back(self):
        self.keyevent("BACK")

    @_safe_wrap
    def app_restart(self, package_name):
        self.adb.stop_app(package_name)
        sleep(1)
        self.adb.start_app(package_name)
        sleep(5)

    @_safe_wrap
    def exists(self, target):
        return self._exists_internal(target)

    def _exists_internal(self, target):
        if isinstance(target, Template):
            pos = self._find_template_pos(target)
            return pos if pos else False
        return False

    @_safe_wrap
    def sleep(self, seconds):
        # 智能休眠：如果时间长，每隔 0.5s 检查一次中断
        end_time = time.time() + seconds
        while time.time() < end_time:
            self.check_interrupt()
            remaining = end_time - time.time()
            time.sleep(min(0.5, remaining))

    # ==========================================
    # 👁️ 数据获取
    # ==========================================
    def get_text(self, area=None):
        return ""

    def parse_number(self, text):
        if not text: return 0
        s = str(text).lower().replace(" ", "").replace(",", "")
        multiplier = 1
        if 'k' in s:
            multiplier = 1000
            s = s.replace('k', '')
        elif 'm' in s:
            multiplier = 1000000
            s = s.replace('m', '')
        try:
            val = float(s)
            return int(val * multiplier)
        except:
            return 0

    # ==========================================
    # 🏠 导航与状态
    # ==========================================
    def check_resolution(self):
        try:
            output = self.adb.shell("wm size")
            if not output: return False
            import re
            match = re.search(r"(\d+)x(\d+)", output)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                if (w == 720 and h == 1280) or (w == 1280 and h == 720): return True
            return False
        except:
            return False

    def ensure_home(self):

        img_home = self.IMG_HOME_CHECK
        if not img_home:
            self.logger.error("核心资源缺失(Home Check)，无法执行回城逻辑！")
            return False
        # img_home = Template(r"assets/images/home/home_check.png")
        img_island = Template(r"assets/images/home/island.png")
        img_town_btn = Template(r"assets/images/home/btn_town.png")
        
        if self.exists(img_home): return True
        if self.exists(img_island):
            self.click(img_town_btn)
            if self.exists(img_home): return True
        if self.exists(img_town_btn):
            self.click(img_town_btn)
            if self.exists(img_home): return True
        
        self.logger.warning("尝试暴力复位...")

        for _ in range(10):
            self.press_back()
            if self.exists(img_home): return True
        return False