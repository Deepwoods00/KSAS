# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel, QSpinBox, QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox, QAbstractSpinBox
from PySide6.QtCore import Qt
from ui.collapsible_box import CollapsibleBox
from i18n.i18n import get_text

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

        # 尝试获取翻译
        trans_key = f"task_{self.task_name.lower()}"
        display_name = get_text(trans_key)
        if display_name == trans_key:
            display_name = self.task_name

        super().__init__(title=display_name, parent=parent, checkable=True)
        self.task_class = task_class

        self.store = None
        self._is_loading = False
        
        self.setChecked(False) # 默认关闭
        self.toggled_enable.connect(self.auto_save)

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
        self.store = store
        # 1. 读取通用开关
        self._is_loading = True
        try:
            # 1. 读取通用开关
            enabled = store.get_cfg(f"modules.{self.task_name.lower()}.enable", False)
            self.setChecked(enabled)
            
            # 2. 读取子类配置 (这里面修改数值将不会触发保存)
            self.load_specific_config(store)
            
        finally:
            # 🔓 解锁！加载完了，现在的变动才是用户的操作
            self._is_loading = False
        
        # 3. 连接信号 (如果尚未连接)
        try:
            store.sig_config_changed.disconnect(self.on_config_changed)
        except:
            pass
        store.sig_config_changed.connect(self.on_config_changed)


    def auto_save(self):
        """[新增] 自动保存槽函数"""
        if self._is_loading:
            return

        if self.store:
            self.save_to_store(self.store)


    def on_config_changed(self, key, value):
        """
        当配置发生变化时（例如后台任务修改了剩余次数），自动刷新 UI
        """
        target_prefix = f"modules.{self.task_name.lower()}"
        if target_prefix in key:
            store = self.sender()
            if store:
                # 🔒 这里也要上锁
                self._is_loading = True
                try:
                    if key == f"{target_prefix}.enable":
                        self.setChecked(value)
                    self.load_specific_config(store)
                finally:
                    self._is_loading = False

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
        self.spin_interval.setSuffix(get_text("unit_sec"))
        self.spin_interval.setValue(3600)
        self.spin_interval.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_interval"), self.spin_interval)
        self.layout.addLayout(form)
        
        lbl = QLabel(get_text("desc_example_task"))
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
        lbl = QLabel(get_text("desc_test_sidebar"))
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

class WolfTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        form = QFormLayout()
        
        # 1. 运行间隔
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(7.5, 1440.0)
        self.spin_interval.setSuffix(get_text("unit_min"))
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(7.5)
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        # 连接信号
        self.spin_interval.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_wolf_interval"), self.spin_interval)
        
        # 2. 攻击次数
        self.spin_attacks = QSpinBox()
        self.spin_attacks.setRange(1, 100)
        self.spin_attacks.setValue(10)
        self.spin_attacks.setButtonSymbols(QAbstractSpinBox.NoButtons)
        # 连接信号
        self.spin_attacks.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_wolf_attacks"), self.spin_attacks)
        
        # 3. 1兵出击
        self.chk_one_soldier = QCheckBox(get_text("cfg_wolf_one_soldier"))
        # 连接信号
        self.chk_one_soldier.toggled.connect(self.auto_save)
        
        form.addRow("", self.chk_one_soldier)
        
        # 4. 英雄策略
        self.combo_hero = QComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any"), "none")
        self.combo_hero.addItem(get_text("opt_hero_diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana"), "diana_fahd")
        # 连接信号
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_wolf_hero"), self.combo_hero)
        
        # 5. 回退策略
        self.combo_fallback = QComboBox()
        self.combo_fallback.addItem(get_text("opt_fallback_default"), "use_default")
        self.combo_fallback.addItem(get_text("opt_fallback_wait"), "wait_1h")
        # 连接信号
        self.combo_fallback.currentIndexChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_wolf_fallback"), self.combo_fallback)
        
        self.layout.addLayout(form)

    # =================================================================
    # 注意：下面的方法必须和 setup_ui 对齐（靠左），不能缩进到 setup_ui 里面！
    # =================================================================

    def load_specific_config(self, store):
        """读取配置并更新 UI"""
        # 1. 运行间隔: 秒(Config) -> 分(UI)
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 450)
        self.spin_interval.setValue(seconds / 60.0)
        
        # 2. 攻击次数
        attacks = store.get_cfg(f"modules.{self.task_name.lower()}.max_attacks", 10)
        self.spin_attacks.setValue(attacks)
        
        # 3. 1兵出击
        one_soldier = store.get_cfg(f"modules.{self.task_name.lower()}.one_soldier", False)
        self.chk_one_soldier.setChecked(one_soldier)
        
        # 4. 英雄策略
        hero_val = store.get_cfg(f"modules.{self.task_name.lower()}.heroes", "none")
        idx = self.combo_hero.findData(hero_val)
        if idx >= 0: 
            self.combo_hero.setCurrentIndex(idx)
        
        # 5. 回退策略
        fallback_val = store.get_cfg(f"modules.{self.task_name.lower()}.fallback_policy", "use_default")
        idx2 = self.combo_fallback.findData(fallback_val)
        if idx2 >= 0: 
            self.combo_fallback.setCurrentIndex(idx2)

    def save_specific_config(self, store):
        """将 UI 的值写入 Config"""
        # print("DEBUG: 正在保存 WolfTask 配置...") # 调试用
        
        # 1. 运行间隔: 分(UI) -> 秒(Config)
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(self.spin_interval.value() * 60))
        
        # 2. 攻击次数
        store.set_cfg(f"modules.{self.task_name.lower()}.max_attacks", self.spin_attacks.value())
        
        # 3. 1兵出击
        store.set_cfg(f"modules.{self.task_name.lower()}.one_soldier", self.chk_one_soldier.isChecked())
        
        # 4. 英雄策略
        store.set_cfg(f"modules.{self.task_name.lower()}.heroes", self.combo_hero.currentData())
        
        # 5. 回退策略
        store.set_cfg(f"modules.{self.task_name.lower()}.fallback_policy", self.combo_fallback.currentData())

class IntelTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        lbl = QLabel(get_text("cfg_intel_desc"))
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

class AllianceHelpConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        # 这里你可以用 get_text 设置标题，或者让 BaseTaskConfigWidget 自动处理
        # self.setTitle("Alliance Help") 

    def setup_ui(self):
        form = QFormLayout()
        
        # 运行间隔 (Interval)
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(120, 7200) # 2分钟(120s) - 2小时(7200s)
        self.spin_interval.setSuffix(" s") # 显示单位为秒，也可以自己换算成分钟显示
        self.spin_interval.setSingleStep(60) # 每次调节步长 60秒
        self.spin_interval.setValue(600)     # 默认值
        self.spin_interval.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_interval", "运行间隔 (秒)"), self.spin_interval)
        
        self.layout.addLayout(form)
        
        # 加个小说明
        lbl = QLabel("检测主页右下角的握手图标并点击。")
        lbl.setStyleSheet("color: #666666; font-size: 9pt;")
        self.layout.addWidget(lbl)

    def load_specific_config(self, store):
        # 读取配置
        val = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 600)
        self.spin_interval.setValue(int(val))

    def save_specific_config(self, store):
        # 保存配置
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", self.spin_interval.value())


class MailTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        # 标题会自动由 BaseTaskConfigWidget 使用 task_mailtask 进行翻译

    def setup_ui(self):
        vbox = QVBoxLayout()

        # 使用 get_text 获取多语言文本
        # 参数2是默认值，防止 yaml 文件还没更新时显示空白
        self.chk_system = QCheckBox(get_text("cfg_mail_system", "System"))
        self.chk_alliance = QCheckBox(get_text("cfg_mail_alliance", "Alliance"))
        self.chk_report = QCheckBox(get_text("cfg_mail_report", "Report"))
        self.chk_war = QCheckBox(get_text("cfg_mail_war", "War"))

        # 连接自动保存
        self.chk_system.toggled.connect(self.auto_save)
        self.chk_alliance.toggled.connect(self.auto_save)
        self.chk_report.toggled.connect(self.auto_save)
        self.chk_war.toggled.connect(self.auto_save)

        vbox.addWidget(self.chk_system)
        vbox.addWidget(self.chk_alliance)
        vbox.addWidget(self.chk_report)
        vbox.addWidget(self.chk_war)
        
        self.layout.addLayout(vbox)
        
        # 间隔设置
        form = QFormLayout()
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(30, 120) 
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_interval.setValue(60)
        self.spin_interval.setSuffix(f" {get_text('unit_min', 'min')}")
        self.spin_interval.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_interval", "Interval"), self.spin_interval)
        self.layout.addLayout(form)

    def load_specific_config(self, store):
        # 默认值：系统和联盟为 True，其他为 False
        self.chk_system.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_system", True))
        self.chk_alliance.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_alliance", True))
        self.chk_report.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_report", False))
        self.chk_war.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_war", False))
        self.spin_interval.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.interval", 3600))
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 3600)
        self.spin_interval.setValue(int(seconds / 60))

    def save_specific_config(self, store):
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_system", self.chk_system.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_alliance", self.chk_alliance.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_report", self.chk_report.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_war", self.chk_war.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", self.spin_interval.value())
        minutes = self.spin_interval.value()
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(minutes * 60))


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
        
        if name == "AllianceHelpTask":
            return AllianceHelpConfigWidget(task_class)
        
        if name == "MailTask":
             return MailTaskConfigWidget(task_class)
            
        # 默认返回基类（只有一个开关）
        return BaseTaskConfigWidget(task_class)
