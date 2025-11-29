# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel, QSpinBox, QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox
from PySide6.QtCore import Qt
from ui.collapsible_box import CollapsibleBox

class BaseTaskConfigWidget(CollapsibleBox):
    """
    所有任务配置小部件的基类。
    自动处理 "启用/禁用" (CollapsibleBox 的 checkable 属性)。
    """
    def __init__(self, task_class, parent=None):
        if task_class.__name__ == "GeneralSettings":
            self.task_name = "General"
        else:
            self.task_name = task_class.__name__

        super().__init__(title=self.task_name, parent=parent, checkable=True)
        self.task_class = task_class



        
        self.setChecked(False) # 默认关闭
        
        # 内部布局
        self.content_layout = QVBoxLayout()
        self.layout = self.content_layout
        self.setup_ui()
        self.setContentLayout(self.content_layout)
        
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
        
        # 3. 连接信号 (如果尚未连接)
        try:
            store.sig_config_changed.disconnect(self.on_config_changed)
        except:
            pass
        store.sig_config_changed.connect(self.on_config_changed)

    def on_config_changed(self, key, value):
        """
        当配置发生变化时（例如后台任务修改了剩余次数），自动刷新 UI
        """
        target_prefix = f"modules.{self.task_name.lower()}"
        if target_prefix in key:
            store = self.sender()
            if store:
                # 如果是 enable 发生变化，更新 checkbox
                if key == f"{target_prefix}.enable":
                    self.setChecked(value)
                
                # 刷新其他配置
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
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        self.setTitle(get_text("task_example"))

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
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        self.setTitle(get_text("task_test_sidebar"))

    def setup_ui(self):
        lbl = QLabel("此任务用于测试侧边栏功能。\n它会检测空闲队列并保存到统计数据中。")
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

from i18n.i18n import get_text

class WolfTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        # Override title with translated text
        self.setTitle(get_text("task_wolf"))

    def setup_ui(self):
        form = QFormLayout()
        
        # 运行间隔 (分钟)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(1.0, 1440.0)
        self.spin_interval.setSuffix(" min")
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(7.5)
        form.addRow(get_text("cfg_wolf_interval"), self.spin_interval)
        
        # 攻击次数
        self.spin_attacks = QSpinBox()
        self.spin_attacks.setRange(1, 100)
        self.spin_attacks.setValue(10)
        form.addRow(get_text("cfg_wolf_attacks"), self.spin_attacks)
        
        # 1兵出击
        self.chk_one_soldier = QCheckBox(get_text("cfg_wolf_one_soldier"))
        form.addRow("", self.chk_one_soldier)
        
        # 英雄策略
        self.combo_hero = QComboBox()
        # 对应: none, diana, diana_fahd
        self.combo_hero.addItem(get_text("opt_hero_any"), "none")
        self.combo_hero.addItem(get_text("opt_hero_diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana"), "diana_fahd")
        form.addRow(get_text("cfg_wolf_hero"), self.combo_hero)
        
        # 回退策略
        self.combo_fallback = QComboBox()
        # 对应: use_default, wait_1h
        self.combo_fallback.addItem(get_text("opt_fallback_default"), "use_default")
        self.combo_fallback.addItem(get_text("opt_fallback_wait"), "wait_1h")
        form.addRow(get_text("cfg_wolf_fallback"), self.combo_fallback)
        
        self.layout.addLayout(form)

    def load_specific_config(self, store):
        # Interval: 秒 -> 分
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 450)
        self.spin_interval.setValue(seconds / 60.0)
        
        self.spin_attacks.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.max_attacks", 10))
        self.chk_one_soldier.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.one_soldier", False))
        
        hero_val = store.get_cfg(f"modules.{self.task_name.lower()}.heroes", "none")
        idx = self.combo_hero.findData(hero_val)
        if idx >= 0: self.combo_hero.setCurrentIndex(idx)
        
        fallback_val = store.get_cfg(f"modules.{self.task_name.lower()}.fallback_policy", "use_default")
        idx2 = self.combo_fallback.findData(fallback_val)
        if idx2 >= 0: self.combo_fallback.setCurrentIndex(idx2)

    def save_specific_config(self, store):
        # Interval: 分 -> 秒
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(self.spin_interval.value() * 60))
        
        store.set_cfg(f"modules.{self.task_name.lower()}.max_attacks", self.spin_attacks.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.one_soldier", self.chk_one_soldier.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.heroes", self.combo_hero.currentData())
        store.set_cfg(f"modules.{self.task_name.lower()}.fallback_policy", self.combo_fallback.currentData())

class IntelTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        self.setTitle(get_text("task_intel"))

    def setup_ui(self):
        lbl = QLabel(get_text("cfg_intel_desc"))
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

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

        if name == "IntelTask":
            return IntelTaskConfigWidget(task_class)
            
        # 默认返回基类（只有一个开关）
        return BaseTaskConfigWidget(task_class)
