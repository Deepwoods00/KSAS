# -*- coding: utf-8 -*-
import os
import sys
import yaml
import logging
# from config import global_config  <-- 移除顶层导入

logger = logging.getLogger("i18n")

# ==========================================
# 📖 翻译缓存 (Translation Cache)
# ==========================================
# 结构: { "zh_CN": {key: value}, "en_US": {key: value} }
_TRANSLATION_CACHE = {}

def load_language(lang_code):
    """
    加载指定语言的 YAML 文件
    :param lang_code: e.g. "zh", "en"
    """
    # 映射: zh_CN -> zh, en_US -> en
    short_lang = "zh" if "zh" in lang_code else "en"
    
    if short_lang in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[short_lang]

    # 获取当前文件所在目录
    if getattr(sys, 'frozen', False):
        # 打包后，资源文件位于 sys._MEIPASS/i18n
        base_dir = os.path.join(sys._MEIPASS, 'i18n')
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    file_path = os.path.join(base_dir, f"{short_lang}.yaml")
    
    data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            logger.info(f"Loaded language pack: {short_lang}.yaml")
        except Exception as e:
            logger.error(f"Failed to load language pack {file_path}: {e}")
    else:
        logger.warning(f"Language pack not found: {file_path}")
        
    _TRANSLATION_CACHE[short_lang] = data
    return data

# 预加载默认语言
load_language("zh")
load_language("en")

# ==========================================
# 🔧 工具函数 (Helper Functions)
# ==========================================

def get_text(key, *args):
    """
    获取翻译文本
    :param key: 字典中的键
    :param args: 如果文本中有 {} 占位符，用这些参数填充
    Usage: get_text("msg_del_warn", "InstanceA")
    """
    # 1. 从全局配置读取语言 (延迟导入以避免循环引用)
    try:
        from config import global_config
        current_lang_code = global_config.get("language", "zh_CN")
    except ImportError:
        current_lang_code = "zh_CN"

    short_lang = "zh" if "zh" in current_lang_code else "en"
    
    # 2. 获取对应语言的字典
    lang_data = _TRANSLATION_CACHE.get(short_lang)
    if not lang_data:
        # 尝试重新加载
        lang_data = load_language(short_lang)
    
    # 3. 查找 Key
    text = lang_data.get(key)
    
    # 4. 如果没找到，尝试回退到中文 (Fallback)
    if text is None and short_lang != "zh":
        fallback_data = _TRANSLATION_CACHE.get("zh")
        if fallback_data:
            text = fallback_data.get(key)
            
    # 5. 还是没找到，直接返回 Key
    if text is None:
        return key
    
    # 6. 格式化参数
    if args:
        try:
            # 确保 text 是字符串
            return str(text).format(*args)
        except Exception as e:
            logger.warning(f"Failed to format translation text [{key}]: {e}")
            return str(text)
            
    return str(text)