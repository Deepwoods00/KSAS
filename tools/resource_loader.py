# tools/resource_loader.py
# -*- coding: utf-8 -*-
import cv2
import numpy as np
from airtest.core.api import Template as AirtestTemplate
from cryptography.fernet import Fernet

# ==============================================================================
# 🔑 解密密钥配置 (必须与加密时的密钥完全一致！)
# ==============================================================================
# 请把 encrypt_tool.py 生成的 b'xxx...' 完整填入下面
# 示例: DECRYPTION_KEY = b'A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v='
DECRYPTION_KEY = b'gMN3RKaTDbu38pLlA3yah7dZYD8XhxBOWeAtY5eNo64=' 

# 初始化解密器
try:
    cipher = Fernet(DECRYPTION_KEY)
except Exception as e:
    print(f"[ResourceLoader] ⚠️ 密钥格式错误或未配置: {e}")
    cipher = None

class MemoryTemplate(AirtestTemplate):
    """
    安全模版类：
    1. 接收加密的二进制流
    2. 内存解密 (AES)
    3. 内存解码 (OpenCV)
    4. 不落地硬盘
    """
    def __init__(self, encrypted_bytes, threshold=None, target_pos=5, record_pos=None, resolution=(), **kwargs):
        self._img_content = None
        
        if encrypted_bytes and cipher:
            try:
                # --- 第1步：解密 ---
                # 如果这里报错，说明密钥不对，或者文件本身没有加密
                decrypted_bytes = cipher.decrypt(encrypted_bytes)
                
                # --- 第2步：解码图片 ---
                # 将二进制流解码为 OpenCV 图像格式
                nparr = np.frombuffer(decrypted_bytes, np.uint8)
                self._img_content = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
                
                if self._img_content is not None:
                    # [可选] 调试时打印，发布时可注释掉
                    # print(f"[MemoryTemplate] ✅ 图片解密加载成功! 尺寸: {self._img_content.shape}")
                    pass
                else:
                    print(f"[MemoryTemplate] ❌ 解密成功但图片解码失败 (数据损坏?)")

            except Exception as e:
                print(f"[MemoryTemplate] ❌ 加载失败: {e}")
                # 常见原因：密钥不匹配，或者KeyAuth填的是未加密的直链
        
        elif not cipher:
            print("[MemoryTemplate] ❌ 致命错误：解密密钥未配置！")
        else:
            print("[MemoryTemplate] ❌ 错误：接收到的数据为空！")

        # 欺骗父类构造函数，传入虚拟路径防止报错
        super().__init__(filename="MEMORY_ASSET", threshold=threshold, target_pos=target_pos, record_pos=record_pos, resolution=resolution, **kwargs)

    def _imread(self):
        # 核心：重写读取方法，直接返回内存中的 OpenCV 图片对象
        return self._img_content

class ResourceLoader:
    _instance = None
    _keyauth_app = None
    _cache = {}  # 缓存下载好的加密数据，避免重复下载

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResourceLoader, cls).__new__(cls)
        return cls._instance

    def initialize(self, keyauth_app):
        """注入登录成功的 keyauth 实例"""
        self._keyauth_app = keyauth_app

    def get_template(self, file_id, threshold=0.9, record_pos=None, resolution=()):
        """
        获取安全模版：先查缓存，没有则下载
        """
        if not self._keyauth_app:
            print("[ResourceLoader] KeyAuth not initialized!")
            return None

        # 1. 检查缓存 (缓存里存的是加密的 bytes)
        if file_id in self._cache:
            # print(f"[ResourceLoader] 使用缓存 ID: {file_id}")
            encrypted_bytes = self._cache[file_id]
        else:
            # 2. 下载
            print(f"[ResourceLoader] 正在从云端下载资源 ID: {file_id} ...")
            try:
                # KeyAuth 的 file 方法会自动处理 Direct Link 下载
                encrypted_bytes = self._keyauth_app.file(file_id)
                
                # 简单的有效性检查
                if not encrypted_bytes or len(encrypted_bytes) < 100:
                    print(f"[ResourceLoader] ⚠️ 下载数据异常，长度仅 {len(encrypted_bytes) if encrypted_bytes else 0} bytes")
                    # 可能是 404 或 401 错误文本
                    return None
                    
                self._cache[file_id] = encrypted_bytes
            except Exception as e:
                print(f"[ResourceLoader] Download Exception: {e}")
                return None

        # 3. 创建并返回内存模版 (解密过程在 MemoryTemplate 内部发生)
        return MemoryTemplate(encrypted_bytes, threshold=threshold, record_pos=record_pos, resolution=resolution)