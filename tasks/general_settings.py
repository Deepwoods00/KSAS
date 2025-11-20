# tasks/general_settings.py
# -*- coding: utf-8 -*-
from tasks.base_task import BaseTask

class GeneralSettings(BaseTask):
    """
    这是一个虚拟任务，不参与调度。
    它的作用仅仅是定义 [通用设置] 的 UI 布局。
    """
    
    @property
    def name(self):
        # 对应 config.json 里的 "general" 模块
        return "General" 
    
    @property
    def priority(self):
        return 0 # 没用，但不写可能会报错

    # 👇 这里定义 UI 上显示什么
    config_schema = [
        {
            "key": "auto_restart", 
            "type": "checkbox", 
            "label": "异常自动重启 (Auto Restart)", 
            "default": True
        },
        {
            "key": "total_march_slots", 
            "type": "spinbox", 
            "label": "行军队列总数 (Total Queues)", 
            "min": 1, 
            "max": 6, 
            "default": 4
        },
        {
            "key": "diana_level", 
            "type": "spinbox", 
            "label": "戴安娜技能等级 (Diana Skill Lvl)", 
            "min": 0, 
            "max": 5, 
            "default": 5
        }
    ]

    def run_impl(self):
        # 这是一个哑巴任务，永远不会被执行
        return True