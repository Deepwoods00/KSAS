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

# Airtest 核心 API
from airtest.core.api import (
    connect_device, set_current, touch, swipe, text, 
    wait, exists, sleep, snapshot, keyevent, Template
)
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import G

# OCR 库引入
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

# ====================================================
# 🔒 全局互斥锁 (Reentrant Lock)
# ====================================================
_ADB_LOCK = threading.RLock()

# ==========================================
# 🧠 全局共享资源 (OCR)
# ==========================================
class GlobalOCR:
    _engine = None
    _lock = threading.Lock()

    @classmethod
    def _init_engine(cls):
        if PaddleOCR is None:
            return None
        # 👇【关键修改】去掉 show_log=False，防止新版报错
        return PaddleOCR(use_angle_cls=False, lang='ch')

    @classmethod
    def safe_ocr(cls, img_array):
        if cls._engine is None:
            with cls._lock:
                if cls._engine is None:
                    cls._engine = cls._init_engine()
        
        if cls._engine is None:
            return []

        with cls._lock:
            try:
                # 直接传图片
                result = cls._engine.ocr(img_array)
                return result
            except Exception as e:
                print(f"[GlobalOCR] 识别报错: {e}")
                return []

# ==========================================
# 🛠️ 实例操作器
# ==========================================
class DeviceOperator:
    def __init__(self, serial, instance_id, data_dir_root="data"):
        self.serial = serial
        self.instance_id = instance_id
        self.logger = logging.getLogger(f"{instance_id}.Device")
        
        self.base_dir = os.path.join(data_dir_root, instance_id)
        self.snapshot_dir = os.path.join(self.base_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self._is_connected = False

    # ==========================================
    # 🛡️ 装饰器 (用于动作，返回 Bool)
    # ==========================================
    def _safe_wrap(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            action_name = func.__name__
            with _ADB_LOCK:
                self._ensure_context()
                try:
                    result = func(self, *args, **kwargs)
                    return True if result is None else result
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
    def connect(self):
        with _ADB_LOCK:
            try:
                uri = f"Android:///{self.serial}?cap_method=JAVACAP&touch_method=ADBTOUCH"
                connect_device(uri)
                self._is_connected = True
                self.logger.info(f"连接成功: {self.serial}")
                return True
            except Exception as e:
                self.logger.error(f"连接失败: {e}")
                self._is_connected = False
                return False

    def _ensure_context(self):
        if self._is_connected:
            try:
                set_current(self.serial)
            except Exception:
                pass

    def _save_snapshot(self, tag):
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{timestamp}_{tag}.png"
            filepath = os.path.join(self.snapshot_dir, filename)
            snapshot(filename=filepath)
            return filepath
        except:
            return None

    # ==========================================
    # 👆 动作执行 (保留装饰器)
    # ==========================================
    @_safe_wrap
    def click(self, target, times=1, offset=(0, 0)):
        for _ in range(times):
            touch(target)
            if times > 1:
                sleep(random.uniform(0.2, 0.5))

    @_safe_wrap
    def swipe_screen(self, direction="up", scale=0.6, area=None):
        if area:
            x1, y1, x2, y2 = map(int, area)
            w, h = x2 - x1, y2 - y1
            base_x, base_y = x1, y1
        else:
            w, h = G.DEVICE.get_current_resolution()
            base_x, base_y = 0, 0
        cx, cy = base_x + w * 0.5, base_y + h * 0.5
        delta_h, delta_w = h * scale * 0.5, w * scale * 0.5
        if direction == "up":    start, end = (cx, cy + delta_h), (cx, cy - delta_h)
        elif direction == "down": start, end = (cx, cy - delta_h), (cx, cy + delta_h)
        elif direction == "left": start, end = (cx + delta_w, cy), (cx - delta_w, cy)
        elif direction == "right": start, end = (cx - delta_w, cy), (cx + delta_w, cy)
        else: return False
        swipe(start, end)
        sleep(0.8)

    @_safe_wrap
    def swipe_until_found(self, target, direction="up", scale=0.5, area=None, max_retry=5):
        for i in range(max_retry):
            time.sleep(0.5)
            if exists(target): return True
            self.logger.info(f"寻找目标... 滑动 #{i+1}")
            self.swipe_screen(direction=direction, scale=scale, area=area)
        return False

    @_safe_wrap
    def pinch(self, mode="in"):
        from airtest.core.api import pinch as at_pinch
        at_pinch(mode=mode, center=None)
        sleep(1.5)

    @_safe_wrap
    def input_text(self, content, confirm=True):
        text(str(content), enter=confirm)
        sleep(1)

    @_safe_wrap
    def press_back(self):
        keyevent("BACK")
        sleep(1)

    @_safe_wrap
    def app_restart(self, package_name):
        from airtest.core.android.android import Android
        dev = G.DEVICE
        if isinstance(dev, Android):
            dev.stop_app(package_name)
            sleep(1)
            dev.start_app(package_name)
            sleep(5)

    @_safe_wrap
    def exists(self, target):
        return True if exists(target) else False

    @_safe_wrap
    def sleep(self, seconds):
        sleep(seconds)

    # ==========================================
    # 👁️ 数据获取 (无装饰器，手动控制返回字符串)
    # ==========================================
    def get_text(self, area=None):
        """OCR 识别 (手动加锁，返回字符串)"""
        with _ADB_LOCK:
            try:
                self._ensure_context()
                temp_path = os.path.join(self.snapshot_dir, "ocr_tmp.png")
                snapshot(filename=temp_path)
                img = cv2.imread(temp_path)
                if img is None: return ""

                if area:
                    x1, y1, x2, y2 = map(int, area)
                    h, w = img.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    img = img[y1:y2, x1:x2]

                # 图像增强
                try:
                    height, width = img.shape[:2]
                    scale = 3
                    zoomed = cv2.resize(img, (width*scale, height*scale), interpolation=cv2.INTER_CUBIC)
                    gray = cv2.cvtColor(zoomed, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
                    final_img = cv2.copyMakeBorder(binary, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                    final_img = cv2.cvtColor(final_img, cv2.COLOR_GRAY2BGR)
                except:
                    final_img = img
            except Exception as e:
                self.logger.error(f"OCR前置操作异常: {e}")
                return ""

        # OCR (自带锁，移出 ADB 锁范围)
        res = GlobalOCR.safe_ocr(final_img)
        if not res: return ""

        try:
            if isinstance(res[0], dict):
                texts = res[0].get('rec_texts', [])
                txt = "".join(texts)
            elif isinstance(res[0], list):
                txt = "".join([line[1][0] for line in res[0]])
            else:
                txt = ""
            return txt.strip()
        except:
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
    # 🏠 导航与状态 (不加装饰器，内部调用原子操作)
    # ==========================================
    def check_resolution(self):
        try:
            from airtest.core.android.adb import ADB
            adb = ADB(self.serial)
            output = adb.shell("wm size")
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
        img_home = Template(r"assets/images/home_check.png")
        img_island = Template(r"assets/images/island.png")
        img_town_btn = Template(r"assets/images/btn_town.png")
        
        if self.exists(img_home): return True
        if self.exists(img_island):
            self.click(img_town_btn)
            if self.exists(img_home): return True
        if self.exists(img_town_btn):
            self.click(img_town_btn)
            if self.exists(img_home): return True
        
        self.logger.warning("尝试暴力复位...")
        for _ in range(3):
            self.press_back()
            if self.exists(img_home): return True
        return False