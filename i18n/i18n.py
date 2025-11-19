# -*- coding: utf-8 -*-

# ==========================================
# 🌍 全局语言设置 (Global Language Setting)
# ==========================================

# 默认语言: 'cn' (中文) / 'en' (English)
CURRENT_LANG = "en"

# ==========================================
# 📖 翻译字典 (Translation Dictionary)
# ==========================================
TEXTS = {
    # --- 侧边栏 (Sidebar) ---
    "app_title": {
        "cn": "KSAS",
        "en": "KSAS"
    },
    "btn_add_instance": {
        "cn": "➕ 添加实例",
        "en": "➕ Add Instance"
    },
    "btn_global_settings": {
        "cn": "⚙️ 设置",
        "en": "⚙️ Settings"
    },
    "btn_del_instance": {
        "cn": "🗑️ 删除",
        "en": "🗑️ Delete"
    },

    # --- 顶部控制区 (Header / Dashboard) ---
    "lbl_default_instance": {
        "cn": "请选择实例",
        "en": "Select Instance"
    },
    "status_offline": {
        "cn": "🔴 离线",
        "en": "🔴 Offline"
    },
    "status_running": {
        "cn": "🟢 运行中",
        "en": "🟢 Running"
    },
    "status_error": {
        "cn": "⚠️ 异常",
        "en": "⚠️ Error"
    },

    # --- 核心切换按钮 (Toggle Button) ---
    # 注意：这里是用状态作为 Key，代码里逻辑判断后取值
    "btn_start": {
        "cn": "▶ 启动",
        "en": "▶ Start"
    },
    "btn_stop": {
        "cn": "⏹ 停止",
        "en": "⏹ Stop"
    },

    # --- 任务列表区 (Task Area) ---
    "col_task_name": {
        "cn": "任务名称",
        "en": "Task Name"
    },
    "btn_task_settings": {
        "cn": "设置",
        "en": "Config"
    },

    # --- 日志区 (Log Area) ---
    "lbl_log_title": {
        "cn": "运行日志",
        "en": "Runtime Log"
    },
    "chk_auto_scroll": {
        "cn": "自动滚动",
        "en": "Auto Scroll"
    },
    "btn_clear_log": {
        "cn": "清空",
        "en": "Clear"
    },

    # --- 弹窗提示 (Messages) ---
    "msg_title_error": {
        "cn": "错误",
        "en": "Error"
    },
    "msg_create_success": {
        "cn": "实例创建成功！",
        "en": "Instance Created!"
    },
    "msg_delete_confirm": {
        "cn": "确定要删除这个实例吗？数据将无法恢复。",
        "en": "Are you sure to delete this instance? Data cannot be recovered."
    }
}

# ==========================================
# 🔧 工具函数 (Helper Functions)
# ==========================================

def get_text(key):
    """
    获取翻译文本
    用法: get_text("btn_start") -> "▶ 启动"
    """
    data = TEXTS.get(key)
    if not data:
        # 如果 Key 没找到，直接返回 Key 本身，方便调试发现漏了啥
        return f"[{key}]"
    
    # 优先取当前语言，取不到就降级用中文，还不行就返回空串
    return data.get(CURRENT_LANG, data.get("cn", ""))

def set_language(lang_code):
    """
    切换全局语言
    :param lang_code: 'cn' or 'en'
    """
    global CURRENT_LANG
    if lang_code in ["cn", "en"]:
        CURRENT_LANG = lang_code