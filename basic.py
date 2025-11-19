# -*- coding: utf-8 -*-
import os
import time
import logging
import random
import threading  # 新增：用于 OCR 锁
import cv2
import numpy as np
from functools import wraps
from datetime import datetime

# Airtest 核心 API
from airtest.core.api import (
    connect_device, set_current, touch, swipe, text, 
    wait, exists, sleep, snapshot, keyevent
)
from airtest.core.error import TargetNotFoundError
from airtest.core.helper import G

# OCR 库引入 (按需加载)
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

# ==========================================
# 🧠 全局共享资源 (Global Shared Resources)
# ==========================================
class GlobalOCR:
    """
    全区唯一的 OCR 服务中心 (单例 + 线程锁)
    所有实例公用这一个引擎，节省内存 (约300-500MB -> 仅一份)。
    """
    _engine = None
    _lock = threading.Lock() # 排队锁

    @classmethod
    def _init_engine(cls):
        """内部初始化方法"""
        if PaddleOCR is None:
            return None
        # use_angle_cls=False 关掉方向检测提速
        # lang='en' 兼容英文和数字
        # show_log=False 关掉刷屏日志
        return PaddleOCR(use_angle_cls=False, lang='ch', show_log=False)

    @classmethod
    def safe_ocr(cls, img_array):
        """
        线程安全的 OCR 识别
        :param img_array: cv2 格式的图片数组
        :return: PaddleOCR 的原始结果 list
        """
        # 1. 懒加载：第一个人用的时候才初始化
        if cls._engine is None:
            with cls._lock:
                # 双重检查锁
                if cls._engine is None:
                    cls._engine = cls._init_engine()
        
        if cls._engine is None:
            return []

        # 2. 排队执行：保证同一时刻只有一个线程在用 OCR
        with cls._lock:
            try:
                # cls=False 不做分类，只做检测和识别
                result = cls._engine.ocr(img_array, cls=False)
                return result
            except Exception as e:
                print(f"[GlobalOCR] 识别报错: {e}")
                return []

# ==========================================
# 🛠️ 实例操作器 (Instance Operator)
# ==========================================
class DeviceOperator:
    """
    KSAS 基础工具箱 (Basic Toolbox)
    职责：封装底层 ADB 操作，提供安全、防崩、带日志和截图的原子指令。
    """

    def __init__(self, serial, instance_id, data_dir_root="data"):
        """
        初始化设备操作器
        :param serial: 设备的 ADB 序列号 (如 emulator-5554)
        :param instance_id: 实例 ID (用于区分日志和截图文件夹)
        """
        self.serial = serial
        self.instance_id = instance_id
        
        # 配置该实例专属的 Logger
        self.logger = logging.getLogger(f"Dev_{instance_id}")
        
        # 初始化文件目录: data/[instance_id]/snapshots/
        self.base_dir = os.path.join(data_dir_root, instance_id)
        self.snapshot_dir = os.path.join(self.base_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self._is_connected = False

    # ==========================================
    # 🛡️ 核心装饰器：钢铁侠战衣 (Safe Wrap)
    # ==========================================
    def _safe_wrap(func):
        """
        [装饰器] 自动处理上下文、异常捕获、截图证据
        所有 Action 级函数都必须加上这个装饰器。
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            action_name = func.__name__
            
            # 1. 确保上下文 (防止多开串台)
            self._ensure_context()
            
            try:
                # 2. 尝试执行原始逻辑
                result = func(self, *args, **kwargs)
                # 如果函数没有返回值，默认视为成功 (True)
                return True if result is None else result
            
            except TargetNotFoundError:
                # 场景：找不到图片
                self.logger.warning(f"[{action_name}] 失败: 目标图片未找到")
                self._save_snapshot(f"{action_name}_404")
                return False
                
            except Exception as e:
                # 场景：断连、卡死或其他报错
                self.logger.error(f"[{action_name}] 异常: {e}")
                self._save_snapshot(f"{action_name}_error")
                return False
                
        return wrapper

    # ==========================================
    # 🔌 系统连接与底层 (System)
    # ==========================================
    def connect(self):
        """连接设备"""
        try:
            # 构造连接字符串，cap_method=MINICAP 截图更快
            uri = f"Android:///{self.serial}?cap_method=MINICAP&touch_method=MAXTOUCH"
            self.logger.info(f"正在连接设备: {self.serial} ...")
            connect_device(uri)
            self._is_connected = True
            self.logger.info("连接成功")
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False

    def _ensure_context(self):
        """强制切换 Airtest 的操作对象到当前设备"""
        if self._is_connected:
            try:
                set_current(self.serial)
            except Exception:
                self.connect()

    def _save_snapshot(self, tag):
        """保存截图证据"""
        try:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{timestamp}_{tag}.png"
            filepath = os.path.join(self.snapshot_dir, filename)
            
            self._ensure_context()
            snapshot(filename=filepath)
            return filepath
        except Exception:
            return None

    @_safe_wrap
    def press_back(self):
        """按物理返回键 (处理广告弹窗神器)"""
        keyevent("BACK")
        sleep(1)

    @_safe_wrap
    def app_restart(self, package_name):
        """重启游戏"""
        from airtest.core.android.android import Android
        dev = G.DEVICE
        if isinstance(dev, Android):
            dev.stop_app(package_name)
            sleep(1)
            dev.start_app(package_name)
            sleep(5)

    # ==========================================
    # 👆 动作执行 (Actions)
    # ==========================================

    @_safe_wrap
    def click(self, target, times=1, offset=(0, 0)):
        """
        点击目标 (带随机防封)
        :param target: 图片 Template 对象 或 (x, y) 坐标
        """
        for _ in range(times):
            touch(target) 
            if times > 1:
                sleep(random.uniform(0.2, 0.5))

    @_safe_wrap
    def swipe_screen(self, direction="up", scale=0.6, area=None):
        """
        滑动屏幕 (支持局部/全屏)
        :param direction: "up", "down", "left", "right"
        :param scale: 滑动幅度 (0.1~0.9)
        :param area: (x1, y1, x2, y2) 限制区域
        """
        if area:
            x1, y1, x2, y2 = map(int, area)
            w = x2 - x1
            h = y2 - y1
            base_x, base_y = x1, y1
        else:
            w, h = G.DEVICE.get_current_resolution()
            base_x, base_y = 0, 0

        cx = base_x + w * 0.5
        cy = base_y + h * 0.5
        
        # 计算偏移
        delta_h = h * scale * 0.5
        delta_w = w * scale * 0.5

        if direction == "up":    # 手指下->上 (内容滚上去)
            start, end = (cx, cy + delta_h), (cx, cy - delta_h)
        elif direction == "down": # 手指上->下 (内容滚下来)
            start, end = (cx, cy - delta_h), (cx, cy + delta_h)
        elif direction == "left": # 手指右->左
            start, end = (cx + delta_w, cy), (cx - delta_w, cy)
        elif direction == "right": # 手指左->右
            start, end = (cx - delta_w, cy), (cx + delta_w, cy)
        else:
            return False

        swipe(start, end)
        sleep(0.8) # 惯性等待

    @_safe_wrap
    def swipe_until_found(self, target, direction="up", scale=0.5, area=None, max_retry=5):
        """滑动查找 (一直滑直到找到图片)"""
        for i in range(max_retry):
            if exists(target):
                return True
            self.logger.info(f"未找到目标，滑动 #{i+1}")
            self.swipe_screen(direction=direction, scale=scale, area=area)
        return False

    @_safe_wrap
    def pinch(self, mode="in"):
        """双指缩放地图: 'in'(缩小/视野大), 'out'(放大)"""
        from airtest.core.api import pinch as at_pinch
        at_pinch(mode=mode, center=None)
        sleep(1.5)

    @_safe_wrap
    def input_text(self, content, confirm=True):
        """输入文字"""
        text(str(content), enter=confirm)
        sleep(1)

    # ==========================================
    # 👁️ 视觉与数据 (Vision & OCR)
    # ==========================================
    
    @_safe_wrap
    def exists(self, target):
        """判断图片是否存在 (返回 Bool)"""
        return True if exists(target) else False

    @_safe_wrap
    def sleep(self, seconds):
        sleep(seconds)

    @_safe_wrap
    def get_text(self, area=None):
        """
        OCR 识别指定区域的文字
        使用 GlobalOCR 单例，线程安全
        :param area: (x1, y1, x2, y2)
        """
        self._ensure_context()
        
        # 1. 截图并保存临时文件
        # (Airtest 的 snapshot 也可以直接返回 bytes，但为了兼容性先存盘再读)
        temp_path = os.path.join(self.snapshot_dir, "ocr_tmp.png")
        snapshot(filename=temp_path)
        
        # 2. 读取并裁剪 (使用 OpenCV)
        img = cv2.imread(temp_path)
        if img is None: return ""

        if area:
            x1, y1, x2, y2 = map(int, area)
            # 边界保护
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            img = img[y1:y2, x1:x2]

        # 3. 调用全局 OCR (这一步会自动排队)
        res = GlobalOCR.safe_ocr(img)
        
        if not res or res[0] is None:
            return ""
        
        # 4. 提取文字
        # PaddleOCR 结果结构: [[[[x,y]..], ('text', conf)], ...]
        txt = " ".join([line[1][0] for line in res[0]])
        return txt.strip()

    def parse_number(self, text):
        """
        [辅助函数] 将 '10.5k' 转换为整数 10500
        """
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
        except ValueError:
            return 0

# 文件结束