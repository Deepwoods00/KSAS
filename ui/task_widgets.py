# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QLabel, QSpinBox, 
    QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox, 
    QAbstractSpinBox, QHBoxLayout, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from i18n.i18n import get_text

# ========================================================
# 🛑 自定义防误触控件 (禁用滚轮修改数值)
# ========================================================

class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        # 忽略滚轮事件，让滚动区域接管（防止误触修改数值）
        event.ignore()

class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

# ========================================================
# 🏗️ 基类定义
# ========================================================

class BaseTaskConfigWidget(QWidget):
    """
    所有任务配置小部件的基类。
    改为平铺布局：顶部标题/开关 -> 分割线 -> 具体配置
    """
    # 定义信号，当启用状态变更时触发
    toggled_enable = Signal(bool)

    def __init__(self, task_class, parent=None):
        super().__init__(parent)
        
        if task_class.__name__ == "GeneralSettings":
            self.task_name = "General"
        else:
            self.task_name = task_class.__name__

        # 尝试获取翻译
        trans_key = f"task_{self.task_name.lower()}"
        display_name = get_text(trans_key)
        if display_name == trans_key:
            display_name = self.task_name

        self.task_class = task_class
        self.store = None
        self._is_loading = False

        # --- 主布局 ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        # 让内容靠上对齐
        self.main_layout.setAlignment(Qt.AlignTop)

        # 1. 顶部区域：标题 + 总开关
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)

        # 标题
        self.title_label = QLabel(display_name)
        self.title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #00695C;")
        top_layout.addWidget(self.title_label)

        # 描述/开关区域
        switch_layout = QHBoxLayout()
        
        # 左侧描述
        lbl_desc = QLabel(get_text("lbl_enable_feature", "启用该功能"))
        lbl_desc.setStyleSheet("font-size: 10pt; font-weight: bold; color: #333333;")
        
        # 详细小字
        lbl_sub = QLabel(get_text("lbl_enable_sub", "将这个任务加入调度器"))
        lbl_sub.setStyleSheet("color: #666666; font-size: 9pt;")
        
        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        text_vbox.addWidget(lbl_desc)
        text_vbox.addWidget(lbl_sub)
        
        switch_layout.addLayout(text_vbox)
        switch_layout.addStretch()

        # 右侧开关
        self.chk_enable = QCheckBox()
        # 自定义开关样式：调整为更精致的大小 (20x20)
        self.chk_enable.setStyleSheet("""
            QCheckBox::indicator { 
                width: 20px; 
                height: 20px; 
                border-radius: 3px;
            }
        """)
        self.chk_enable.setCursor(Qt.PointingHandCursor)
        self.chk_enable.toggled.connect(self.on_user_toggled)
        switch_layout.addWidget(self.chk_enable)

        top_layout.addLayout(switch_layout)
        
        # 2. 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #B2DFDB; max-height: 1px;")
        
        self.main_layout.addWidget(top_container)
        self.main_layout.addWidget(line)

        # 3. 具体配置容器
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 10, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignTop)
        
        # 调用子类实现 UI
        self.setup_ui()
        
        self.main_layout.addWidget(self.content_container)
        
        # 底部弹簧，让内容靠上
        self.main_layout.addStretch()

    def setup_ui(self):
        """【子类重写】在 self.content_layout 里添加具体的控件"""
        pass
        
    def load_from_store(self, store):
        """从 DataStore 读取配置并刷新 UI"""
        self.store = store
        self._is_loading = True
        try:
            # 1. 读取通用开关
            enabled = store.get_cfg(f"modules.{self.task_name.lower()}.enable", False)
            self.chk_enable.setChecked(enabled)
            self.update_content_visibility(enabled)
            
            # 2. 读取子类配置
            self.load_specific_config(store)
        finally:
            self._is_loading = False
        
        # 连接信号
        try:
            store.sig_config_changed.disconnect(self.on_config_changed)
        except(RuntimeError, TypeError):
            pass
        store.sig_config_changed.connect(self.on_config_changed)

    def on_user_toggled(self, checked):
        """用户点击开关"""
        self.update_content_visibility(checked)
        self.toggled_enable.emit(checked)
        self.auto_save()

    def update_content_visibility(self, checked):
        """根据开关状态，决定下方内容是否变灰 (可选)"""
        self.content_container.setEnabled(checked)

    def isChecked(self):
        return self.chk_enable.isChecked()
    
    def setChecked(self, checked):
        """供外部调用修改状态"""
        self.chk_enable.setChecked(checked)

    def auto_save(self):
        """自动保存槽函数"""
        if self._is_loading:
            return
        if self.store:
            self.save_to_store(self.store)

    def on_config_changed(self, key, value):
        target_prefix = f"modules.{self.task_name.lower()}"
        if target_prefix in key:
            store = self.sender()
            if store:
                self._is_loading = True
                try:
                    if key == f"{target_prefix}.enable":
                        self.chk_enable.setChecked(value)
                        self.update_content_visibility(value)
                    self.load_specific_config(store)
                finally:
                    self._is_loading = False

    def save_to_store(self, store):
        # 1. 保存通用开关
        store.set_cfg(f"modules.{self.task_name.lower()}.enable", self.isChecked())
        # 2. 保存子类特定配置
        self.save_specific_config(store)

    def load_specific_config(self, store):
        pass

    def save_specific_config(self, store):
        pass

    # 为了兼容旧代码，将 layout 属性指向内容布局
    @property
    def layout(self):
        return self.content_layout

# ========================================================
# 👇 具体任务配置实现 (已更新时间单位为分钟)
# ========================================================

class ExampleTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        form = QFormLayout()
        self.spin_interval = NoScrollSpinBox()
        # [修改] 改为分钟: 1分钟 - 24小时
        self.spin_interval.setRange(1, 1440) 
        # [修改] 单位改为 min
        self.spin_interval.setSuffix(f" {get_text('unit_min', 'min')}")
        self.spin_interval.setValue(60) # 默认 60分钟
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_interval.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_interval"), self.spin_interval)
        self.layout.addLayout(form)
        
        lbl = QLabel(get_text("desc_example_task"))
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        self.layout.addWidget(lbl)

    def load_specific_config(self, store):
        # Config 存的是秒，UI 显示分钟
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 3600)
        self.spin_interval.setValue(int(seconds / 60))

    def save_specific_config(self, store):
        # UI 是分钟，保存为秒
        minutes = self.spin_interval.value()
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(minutes * 60))

class TestSidebarTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        lbl = QLabel(get_text("desc_test_sidebar"))
        lbl.setStyleSheet("color: #666666; font-style: italic;")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)

class WolfTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        group = QGroupBox(get_text("grp_settings", "配置"))
        form = QFormLayout(group)
        
        self.spin_interval = NoScrollDoubleSpinBox()
        self.spin_interval.setRange(7.5, 1440.0)
        self.spin_interval.setSuffix(f" {get_text('unit_min', 'min')}") # 确保单位一致
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_interval.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_wolf_interval"), self.spin_interval)
        
        self.spin_attacks = NoScrollSpinBox()
        self.spin_attacks.setRange(1, 100)
        self.spin_attacks.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_attacks.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_wolf_attacks"), self.spin_attacks)
        
        self.chk_one_soldier = QCheckBox(get_text("cfg_wolf_one_soldier"))
        self.chk_one_soldier.toggled.connect(self.auto_save)
        form.addRow("", self.chk_one_soldier)
        
        self.combo_hero = NoScrollComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any"), "none")
        self.combo_hero.addItem(get_text("opt_hero_diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana"), "diana_fahd")
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_wolf_hero"), self.combo_hero)
        
        self.combo_fallback = NoScrollComboBox()
        self.combo_fallback.addItem(get_text("opt_fallback_default"), "use_default")
        self.combo_fallback.addItem(get_text("opt_fallback_wait"), "wait_1h")
        self.combo_fallback.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_wolf_fallback"), self.combo_fallback)
        
        self.layout.addWidget(group)

    def load_specific_config(self, store):
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
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(self.spin_interval.value() * 60))
        store.set_cfg(f"modules.{self.task_name.lower()}.max_attacks", self.spin_attacks.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.one_soldier", self.chk_one_soldier.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.heroes", self.combo_hero.currentData())
        store.set_cfg(f"modules.{self.task_name.lower()}.fallback_policy", self.combo_fallback.currentData())

class BeastTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        group = QGroupBox(get_text("grp_settings", "配置"))
        form = QFormLayout(group)
        
        self.spin_level = NoScrollSpinBox()
        self.spin_level.setRange(1, 30)
        self.spin_level.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_level.setSuffix(" Lv")
        self.spin_level.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_target_level"), self.spin_level)

        self.spin_remaining = NoScrollSpinBox()
        self.spin_remaining.setRange(0, 100)
        self.spin_remaining.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_remaining.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_remaining_attacks"), self.spin_remaining)

        self.spin_queues = NoScrollSpinBox()
        self.spin_queues.setRange(1, 6)
        self.spin_queues.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_queues.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_concurrent_queues"), self.spin_queues)

        self.combo_hero = NoScrollComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any"), "any")
        self.combo_hero.addItem(get_text("opt_hero_diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana"), "diana_fahd")
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_hero_mode"), self.combo_hero)

        self.combo_soldier = NoScrollComboBox()
        self.combo_soldier.addItem(get_text("opt_soldier_full"), "full")
        self.combo_soldier.addItem(get_text("opt_soldier_equal"), "equal")
        self.combo_soldier.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_soldier_mode"), self.combo_soldier)

        self.layout.addWidget(group)

    def load_specific_config(self, store):
        self.spin_level.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.target_level", 1))
        self.spin_remaining.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.remaining_attacks", 10))
        self.spin_queues.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.concurrent_queues", 1))
        
        hero_val = store.get_cfg(f"modules.{self.task_name.lower()}.hero_mode", "any")
        idx_h = self.combo_hero.findData(hero_val)
        if idx_h >= 0: self.combo_hero.setCurrentIndex(idx_h)

        soldier_val = store.get_cfg(f"modules.{self.task_name.lower()}.soldier_mode", "full")
        idx_s = self.combo_soldier.findData(soldier_val)
        if idx_s >= 0: self.combo_soldier.setCurrentIndex(idx_s)

    def save_specific_config(self, store):
        store.set_cfg(f"modules.{self.task_name.lower()}.target_level", self.spin_level.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.remaining_attacks", self.spin_remaining.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.concurrent_queues", self.spin_queues.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.hero_mode", self.combo_hero.currentData())
        store.set_cfg(f"modules.{self.task_name.lower()}.soldier_mode", self.combo_soldier.currentData())

class RallyTaskConfigWidget(BeastTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        self.spin_level.setRange(1, 7) 

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

    def setup_ui(self):
        form = QFormLayout()
        self.spin_interval = NoScrollSpinBox()
        # [修改] 2分钟 - 120分钟 (原 120-7200秒)
        self.spin_interval.setRange(2, 120) 
        self.spin_interval.setSuffix(f" {get_text('unit_min', 'min')}")
        self.spin_interval.setSingleStep(1) # 1分钟步长
        self.spin_interval.setValue(10)     # 默认10分钟
        # [修改] 隐藏按钮
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_interval.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_interval", "运行间隔 (分)"), self.spin_interval)
        self.layout.addLayout(form)
        
        lbl = QLabel("检测主页右下角的握手图标并点击。")
        lbl.setStyleSheet("color: #666666; font-size: 9pt;")
        self.layout.addWidget(lbl)

    def load_specific_config(self, store):
        # 转换: 秒 -> 分
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 600)
        self.spin_interval.setValue(int(seconds / 60))

    def save_specific_config(self, store):
        # 转换: 分 -> 秒
        minutes = self.spin_interval.value()
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(minutes * 60))

class MailTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        group = QGroupBox(get_text("grp_options", "选项"))
        vbox = QVBoxLayout(group)

        self.chk_system = QCheckBox(get_text("cfg_mail_system", "System"))
        self.chk_alliance = QCheckBox(get_text("cfg_mail_alliance", "Alliance"))
        self.chk_report = QCheckBox(get_text("cfg_mail_report", "Report"))
        self.chk_war = QCheckBox(get_text("cfg_mail_war", "War"))

        self.chk_system.toggled.connect(self.auto_save)
        self.chk_alliance.toggled.connect(self.auto_save)
        self.chk_report.toggled.connect(self.auto_save)
        self.chk_war.toggled.connect(self.auto_save)

        vbox.addWidget(self.chk_system)
        vbox.addWidget(self.chk_alliance)
        vbox.addWidget(self.chk_report)
        vbox.addWidget(self.chk_war)
        self.layout.addWidget(group)
        
        form = QFormLayout()
        self.spin_interval = NoScrollSpinBox()
        self.spin_interval.setRange(30, 120) 
        self.spin_interval.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_interval.setValue(60)
        self.spin_interval.setSuffix(f" {get_text('unit_min', 'min')}")
        self.spin_interval.valueChanged.connect(self.auto_save)
        
        form.addRow(get_text("cfg_interval", "Interval"), self.spin_interval)
        self.layout.addLayout(form)

    def load_specific_config(self, store):
        self.chk_system.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_system", True))
        self.chk_alliance.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_alliance", True))
        self.chk_report.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_report", False))
        self.chk_war.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.collect_war", False))
        seconds = store.get_cfg(f"modules.{self.task_name.lower()}.interval", 3600)
        self.spin_interval.setValue(int(seconds / 60))

    def save_specific_config(self, store):
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_system", self.chk_system.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_alliance", self.chk_alliance.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_report", self.chk_report.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.collect_war", self.chk_war.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.interval", int(self.spin_interval.value() * 60))

class StaminaControlConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        group = QGroupBox(get_text("grp_settings", "设置"))
        form = QFormLayout(group)
        
        self.combo_method = NoScrollComboBox()
        self.combo_method.addItem(get_text("opt_dump_beast", "Beast"), "beast")
        self.combo_method.addItem(get_text("opt_dump_rally", "Rally"), "rally")
        self.combo_method.addItem(get_text("opt_dump_wolf", "Wolf"), "wolf")
        self.combo_method.currentIndexChanged.connect(self.on_method_changed)
        self.combo_method.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_dump_method", "Dump Method"), self.combo_method)
        
        self.spin_level = NoScrollSpinBox()
        self.spin_level.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_level.setSuffix(" Lv")
        self.spin_level.valueChanged.connect(self.auto_save)
        self.lbl_level = QLabel(get_text("cfg_dump_level", "Target Level"))
        form.addRow(self.lbl_level, self.spin_level)
        
        self.chk_one_soldier = QCheckBox(get_text("cfg_wolf_one_soldier", "Use 1 Soldier"))
        self.chk_one_soldier.toggled.connect(self.auto_save)
        form.addRow("", self.chk_one_soldier)
        
        self.spin_reserve = NoScrollSpinBox()
        self.spin_reserve.setRange(0, 200)
        self.spin_reserve.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_reserve.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_reserve_stamina", "Reserve Limit"), self.spin_reserve)
        
        self.combo_hero = NoScrollComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any", "Any"), "any")
        self.combo_hero.addItem(get_text("opt_hero_diana", "Diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana", "Diana + Fahd"), "diana_fahd")
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_hero_mode", "Heroes"), self.combo_hero)
        
        self.layout.addWidget(group)
        self.on_method_changed()

    def on_method_changed(self):
        method = self.combo_method.currentData()
        if method == "wolf":
            self.lbl_level.hide()
            self.spin_level.hide()
            self.chk_one_soldier.show()
        else:
            self.lbl_level.show()
            self.spin_level.show()
            self.chk_one_soldier.hide()
            if method == "rally":
                self.spin_level.setRange(1, 7)
                if self.spin_level.value() > 7: self.spin_level.setValue(7)
            else:
                self.spin_level.setRange(1, 30)

    def load_specific_config(self, store):
        method = store.get_cfg(f"modules.{self.task_name.lower()}.dump_method", "beast")
        idx = self.combo_method.findData(method)
        if idx >= 0: self.combo_method.setCurrentIndex(idx)
        
        self.spin_level.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.dump_level", 25))
        self.chk_one_soldier.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.dump_one_soldier", True))
        self.spin_reserve.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.reserve_stamina", 190))
        
        hero = store.get_cfg(f"modules.{self.task_name.lower()}.hero_mode", "diana_fahd")
        idx_h = self.combo_hero.findData(hero)
        if idx_h >= 0: self.combo_hero.setCurrentIndex(idx_h)
        
        self.on_method_changed()

    def save_specific_config(self, store):
        store.set_cfg(f"modules.{self.task_name.lower()}.dump_method", self.combo_method.currentData())
        store.set_cfg(f"modules.{self.task_name.lower()}.dump_level", self.spin_level.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.dump_one_soldier", self.chk_one_soldier.isChecked())
        store.set_cfg(f"modules.{self.task_name.lower()}.reserve_stamina", self.spin_reserve.value())
        store.set_cfg(f"modules.{self.task_name.lower()}.hero_mode", self.combo_hero.currentData())

class TroopTrainingConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        self.troop_controls = {} 
        super().__init__(task_class, parent)

    def setup_ui(self):
        troops = [
            ("infantry", "lbl_infantry_settings"),
            ("lancer",   "lbl_lancer_settings"),
            ("marksman", "lbl_marksman_settings")
        ]
        for prefix, label_key in troops:
            self._create_troop_section(prefix, get_text(label_key))
        self._create_time_section()

    def _create_troop_section(self, prefix, title):
        group = QGroupBox(title)
        group.setCheckable(True) 
        group.setChecked(False)
        group.toggled.connect(self.auto_save)
        
        form = QFormLayout(group)
        
        spin_max = NoScrollSpinBox()
        spin_max.setRange(1, 10)
        spin_max.setValue(10)
        spin_max.setSuffix(" Lv")
        spin_max.setButtonSymbols(QAbstractSpinBox.NoButtons) 
        spin_max.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_max_unlock_level"), spin_max)
        
        combo_mode = NoScrollComboBox()
        combo_mode.addItem(get_text("opt_mode_train_new"), "train")
        combo_mode.addItem(get_text("opt_mode_promote"), "promote")
        combo_mode.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_train_mode"), combo_mode)
        
        lbl_target = QLabel(get_text("cfg_operate_level"))
        spin_target = NoScrollSpinBox()
        spin_target.setRange(1, 10)
        spin_target.setValue(9)
        spin_target.setSuffix(" Lv")
        spin_target.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin_target.valueChanged.connect(self.auto_save)
        form.addRow(lbl_target, spin_target)
        
        self.layout.addWidget(group)
        
        controls = {
            "group": group,
            "spin_max": spin_max,
            "combo_mode": combo_mode,
            "lbl_target": lbl_target,
            "spin_target": spin_target
        }
        self.troop_controls[prefix] = controls

        combo_mode.currentIndexChanged.connect(lambda idx, c=controls: self._on_mode_changed(c))
        spin_max.valueChanged.connect(lambda val, c=controls: self._on_max_level_changed(c))

    def _create_time_section(self):
        group = QGroupBox(get_text("lbl_time_settings"))
        hbox = QHBoxLayout(group)
        self.spin_h = NoScrollSpinBox()
        self.spin_h.setRange(0, 24)
        self.spin_h.setSuffix(" h")
        self.spin_h.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_h.valueChanged.connect(self.auto_save)
        
        self.spin_m = NoScrollSpinBox()
        self.spin_m.setRange(0, 59)
        self.spin_m.setSuffix(" m")
        self.spin_m.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_m.valueChanged.connect(self.auto_save)
        
        hbox.addWidget(QLabel(get_text("cfg_train_time_h")))
        hbox.addWidget(self.spin_h)
        hbox.addWidget(QLabel(get_text("cfg_train_time_m")))
        hbox.addWidget(self.spin_m)
        self.layout.addWidget(group)

    def _on_mode_changed(self, controls):
        mode = controls["combo_mode"].currentData()
        max_lv = controls["spin_max"].value()
        spin_target = controls["spin_target"]
        lbl_target = controls["lbl_target"]

        spin_target.blockSignals(True)
        suggested_val = max(1, max_lv - 1)

        if mode == "train":
            lbl_target.setText(get_text("cfg_target_level_label", "目标等级"))
            spin_target.setMaximum(max_lv)
            spin_target.setValue(suggested_val)
        else:
            lbl_target.setText(get_text("cfg_promote_from_label", "晋升来源"))
            limit = max(1, max_lv - 1)
            spin_target.setMaximum(limit)
            spin_target.setValue(limit)
            
        spin_target.blockSignals(False)
        self.auto_save()

    def _on_max_level_changed(self, controls):
        self._on_mode_changed(controls)

    def load_specific_config(self, store):
        for prefix, controls in self.troop_controls.items():
            enabled = store.get_cfg(f"modules.trooptrainingtask.{prefix}_enable", False)
            controls["group"].setChecked(enabled)
            max_lv = store.get_cfg(f"modules.trooptrainingtask.{prefix}_max_level", 10)
            controls["spin_max"].setValue(max_lv)
            mode = store.get_cfg(f"modules.trooptrainingtask.{prefix}_mode", "train")
            idx = controls["combo_mode"].findData(mode)
            if idx >= 0: controls["combo_mode"].setCurrentIndex(idx)
            target = store.get_cfg(f"modules.trooptrainingtask.{prefix}_target_level", 9)
            controls["spin_target"].setValue(target)
            
            if mode == "train":
                controls["lbl_target"].setText(get_text("cfg_target_level_label", "目标等级"))
            else:
                controls["lbl_target"].setText(get_text("cfg_promote_from_label", "晋升来源"))

        h = store.get_cfg("modules.trooptrainingtask.train_time_h", 3)
        m = store.get_cfg("modules.trooptrainingtask.train_time_m", 0)
        self.spin_h.setValue(h)
        self.spin_m.setValue(m)

    def save_specific_config(self, store):
        for prefix, controls in self.troop_controls.items():
            store.set_cfg(f"modules.trooptrainingtask.{prefix}_enable", controls["group"].isChecked())
            store.set_cfg(f"modules.trooptrainingtask.{prefix}_max_level", controls["spin_max"].value())
            store.set_cfg(f"modules.trooptrainingtask.{prefix}_mode", controls["combo_mode"].currentData())
            store.set_cfg(f"modules.trooptrainingtask.{prefix}_target_level", controls["spin_target"].value())
        store.set_cfg("modules.trooptrainingtask.train_time_h", self.spin_h.value())
        store.set_cfg("modules.trooptrainingtask.train_time_m", self.spin_m.value())

class TaskWidgetFactory:
    @staticmethod
    def create_widget(task_class):
        name = task_class.__name__
        
        if name == "ExampleTask": return ExampleTaskConfigWidget(task_class)
        if name == "TestSidebarTask": return TestSidebarTaskConfigWidget(task_class)
        if name == "BeastTask": return BeastTaskConfigWidget(task_class)
        if name == "RallyTask": return RallyTaskConfigWidget(task_class)
        if name == "WolfTask": return WolfTaskConfigWidget(task_class)
        if name == "IntelTask": return IntelTaskConfigWidget(task_class)
        if name == "AllianceHelpTask": return AllianceHelpConfigWidget(task_class)
        if name == "MailTask": return MailTaskConfigWidget(task_class)
        if name == "StaminaControlTask": return StaminaControlConfigWidget(task_class)
        if name == "TroopTrainingTask": return TroopTrainingConfigWidget(task_class)
            
        return BaseTaskConfigWidget(task_class)