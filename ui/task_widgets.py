# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel, QSpinBox, QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox
from PySide6.QtCore import Qt

class BaseTaskConfigWidget(QGroupBox):
    """
    所有任务配置小部件的基类。
    自动处理 "启用/禁用" (GroupBox 的 checkable 属性)。
    """
    def __init__(self, task_class, parent=None):
        super().__init__(parent)
        self.task_class = task_class



        
        if task_class.__name__ == "GeneralSettings":
            self.task_name = "General"
        else:
            self.task_name = task_class.__name__
        
        # 设置 GroupBox 标题和开关
        self.setTitle(self.task_name)
        self.setCheckable(True)
        self.setChecked(False) # 默认关闭
        
        # 内部布局
        self.layout = QVBoxLayout(self)
        self.setup_ui()
        
    def setup_ui(self):
        """
        【子类重写】在 self.layout 里添加具体的控件
        """
        pass
        
    def load_from_store(self, store):
        """
        从 DataStore 读取配置并刷新 UI
        """
        # 1. 读取通用开关
        # Key 格式: modules.exampletask.enable
        enabled = store.get_cfg(f"modules.{self.task_name.lower()}.enable", False)
        self.setChecked(enabled)
        
        # 2. 读取子类特定配置
        self.load_specific_config(store)
        
    def save_to_store(self, store):
        """
        将 UI 当前状态保存到 DataStore
        """
        # 1. 保存通用开关
        store.set_cfg(f"modules.{self.task_name.lower()}.enable", self.isChecked())
        
        # 2. 保存子类特定配置
        self.save_specific_config(store)

    def load_specific_config(self, store):
        """【子类重写】读取特定参数"""
        pass

    def save_specific_config(self, store):
        """【子类重写】保存特定参数"""
        pass

# ========================================================
# 👇 在这里实现各个任务的具体配置卡片
# ========================================================

class ExampleTaskConfigWidget(BaseTaskConfigWidget):
    def setup_ui(self):
        form = QFormLayout()
        
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(60, 86400)
        self.spin_interval.setSuffix(" 秒")
        self.spin_interval.setValue(3600)
        
        form.addRow("运行间隔:", self.spin_interval)
        self.layout.addLayout(form)
        
        lbl = QLabel("这是一个示例任务，没什么好配置的。")
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        self.layout.addWidget(lbl)

    def load_specific_config(self, store):
        val = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 3600)
        self.spin_interval.setValue(int(val))

    def save_specific_config(self, store):
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", self.spin_interval.value())

class TestSidebarTaskConfigWidget(BaseTaskConfigWidget):
    def setup_ui(self):
        lbl = QLabel("此任务用于测试侧边栏功能。\n它会检测空闲队列并保存到统计数据中。")
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

class WolfTaskConfigWidget(BaseTaskConfigWidget):
    def setup_ui(self):
        form = QFormLayout()
        
        # 运行间隔 (分钟)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(7.5, 1440.0) # Min 7.5 mins
        self.spin_interval.setSuffix(" 分钟")
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(7.5)
        form.addRow("运行间隔:", self.spin_interval)
        
        # 攻击次数
        self.spin_attacks = QSpinBox()
        self.spin_attacks.setRange(0, 9999)
        self.spin_attacks.setValue(10)
        form.addRow("攻击次数:", self.spin_attacks)
        
        # 士兵数量
        self.spin_soldiers = QSpinBox()
        self.spin_soldiers.setRange(0, 500000)
        self.spin_soldiers.setSingleStep(1000)
        self.spin_soldiers.setValue(10000)
        form.addRow("士兵数量:", self.spin_soldiers)
        
        # 英雄策略
        self.combo_hero = QComboBox()
        self.combo_hero.addItems(["不限制", "仅戴安娜", "法赫德 + 戴安娜"])
        form.addRow("英雄策略:", self.combo_hero)
        
        self.layout.addLayout(form)

    def load_specific_config(self, store):
        # Interval: 秒 -> 分
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 450)
        self.spin_interval.setValue(seconds / 60.0)
        
        self.spin_attacks.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.attacks", 10))
        self.spin_soldiers.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.soldiers", 10000))
        self.combo_hero.setCurrentIndex(store.get_cfg(f"modules.{self.task_name.lower()}.hero_strategy", 0))

    def save_specific_config(self, store):
        # Interval: 分 -> 秒
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(self.spin_interval.value() * 60))
        
        store.set_cfg(f"modules.{self.task_name.lower()}.attacks", self.spin_attacks.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.soldiers", self.spin_soldiers.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.hero_strategy", self.combo_hero.currentIndex())

# ========================================================
# 🏭 工厂类
# ========================================================

class TaskWidgetFactory:
    @staticmethod
    def create_widget(task_class):
        name = task_class.__name__
        
        if name == "ExampleTask":
            return ExampleTaskConfigWidget(task_class)
        
        if name == "TestSidebarTask":
            return TestSidebarTaskConfigWidget(task_class)
            
        if name == "WolfTask":
            return WolfTaskConfigWidget(task_class)
            
        # 默认返回基类（只有一个开关）
        return BaseTaskConfigWidget(task_class)
