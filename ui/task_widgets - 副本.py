# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel, QSpinBox, QGroupBox, QFormLayout, QDoubleSpinBox, QComboBox, QAbstractSpinBox, QHBoxLayout
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
        except(RuntimeError, TypeError):
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

class BeastTaskConfigWidget(BaseTaskConfigWidget):
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        form = QFormLayout()
        
        # 1. 目标等级 (Target Level)
        self.spin_level = QSpinBox()
        self.spin_level.setRange(1, 30)
        self.spin_level.setButtonSymbols(QAbstractSpinBox.NoButtons) # 去掉箭头
        self.spin_level.setAlignment(Qt.AlignCenter)
        self.spin_level.setSuffix(" Lv")
        self.spin_level.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_target_level"), self.spin_level)

        # 2. 剩余次数 (Remaining)
        self.spin_remaining = QSpinBox()
        self.spin_remaining.setRange(0, 100)
        self.spin_remaining.setButtonSymbols(QAbstractSpinBox.NoButtons) # 去掉箭头
        self.spin_remaining.setAlignment(Qt.AlignCenter)
        self.spin_remaining.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_remaining_attacks"), self.spin_remaining)

        # 3. 并发队列 (Concurrent Queues)
        self.spin_queues = QSpinBox()
        self.spin_queues.setRange(1, 6)
        self.spin_queues.setButtonSymbols(QAbstractSpinBox.NoButtons) # 去掉箭头
        self.spin_queues.setAlignment(Qt.AlignCenter)
        self.spin_queues.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_concurrent_queues"), self.spin_queues)

        # 4. 英雄模式 (Hero Mode)
        self.combo_hero = QComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any"), "any")
        self.combo_hero.addItem(get_text("opt_hero_diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana"), "diana_fahd")
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_hero_mode"), self.combo_hero)

        # 5. 兵力模式 (Soldier Mode)
        self.combo_soldier = QComboBox()
        self.combo_soldier.addItem(get_text("opt_soldier_full"), "full")
        self.combo_soldier.addItem(get_text("opt_soldier_equal"), "equal")
        self.combo_soldier.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_soldier_mode"), self.combo_soldier)

        self.layout.addLayout(form)

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
    """
    直接继承 BeastTaskConfigWidget，复用 UI 结构。
    因为它们配置项完全一样，只是保存的 key 前缀不同（由 self.task_name 自动处理）。
    """
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)
        # 可以在这里微调 Ranger，例如巨兽等级通常只有 1-8
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

class StaminaControlConfigWidget(BaseTaskConfigWidget):
    """体力管理专用配置面板，支持动态显隐"""
    def __init__(self, task_class, parent=None):
        super().__init__(task_class, parent)

    def setup_ui(self):
        form = QFormLayout()
        
        # 1. 泄洪方式
        self.combo_method = QComboBox()
        self.combo_method.addItem(get_text("opt_dump_beast", "Beast"), "beast")
        self.combo_method.addItem(get_text("opt_dump_rally", "Rally"), "rally")
        self.combo_method.addItem(get_text("opt_dump_wolf", "Wolf"), "wolf")
        self.combo_method.currentIndexChanged.connect(self.on_method_changed)
        self.combo_method.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_dump_method", "Dump Method"), self.combo_method)
        
        # 2. 泄洪等级 (Beast/Rally 用)
        self.spin_level = QSpinBox()
        self.spin_level.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_level.setSuffix(" Lv")
        self.spin_level.valueChanged.connect(self.auto_save)
        # 获取 label 引用以便控制显隐
        self.lbl_level = QLabel(get_text("cfg_dump_level", "Target Level"))
        form.addRow(self.lbl_level, self.spin_level)
        
        # 3. 1兵出击 (Wolf 用)
        self.chk_one_soldier = QCheckBox(get_text("cfg_wolf_one_soldier", "Use 1 Soldier"))
        self.chk_one_soldier.toggled.connect(self.auto_save)
        form.addRow("", self.chk_one_soldier)
        
        # 4. 维护阈值
        self.spin_reserve = QSpinBox()
        self.spin_reserve.setRange(0, 200)
        self.spin_reserve.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_reserve.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_reserve_stamina", "Reserve Limit"), self.spin_reserve)
        
        # 5. 英雄策略
        self.combo_hero = QComboBox()
        self.combo_hero.addItem(get_text("opt_hero_any", "Any"), "any")
        self.combo_hero.addItem(get_text("opt_hero_diana", "Diana"), "diana")
        self.combo_hero.addItem(get_text("opt_hero_fahd_diana", "Diana + Fahd"), "diana_fahd")
        self.combo_hero.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_hero_mode", "Heroes"), self.combo_hero)
        
        self.layout.addLayout(form)
        
        # 初始化状态
        self.on_method_changed()

    def on_method_changed(self):
        """根据选择的方法动态显隐控件"""
        method = self.combo_method.currentData()
        
        if method == "wolf":
            # Wolf 模式: 隐藏等级，显示1兵
            self.lbl_level.hide()
            self.spin_level.hide()
            self.chk_one_soldier.show()
        else:
            # Beast/Rally 模式: 显示等级，隐藏1兵
            self.lbl_level.show()
            self.spin_level.show()
            self.chk_one_soldier.hide()
            
            # 动态调整等级范围
            if method == "rally":
                self.spin_level.setRange(1, 7)
                # 如果当前值超标，自动修正
                if self.spin_level.value() > 7: self.spin_level.setValue(7)
            else:
                self.spin_level.setRange(1, 30)

    def load_specific_config(self, store):
        # Method
        method = store.get_cfg(f"modules.{self.task_name.lower()}.dump_method", "beast")
        idx = self.combo_method.findData(method)
        if idx >= 0: self.combo_method.setCurrentIndex(idx)
        
        # Level
        self.spin_level.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.dump_level", 25))
        
        # One Soldier
        self.chk_one_soldier.setChecked(store.get_cfg(f"modules.{self.task_name.lower()}.dump_one_soldier", True))
        
        # Reserve
        self.spin_reserve.setValue(store.get_cfg(f"modules.{self.task_name.lower()}.reserve_stamina", 190))
        
        # Hero
        hero = store.get_cfg(f"modules.{self.task_name.lower()}.hero_mode", "diana_fahd")
        idx_h = self.combo_hero.findData(hero)
        if idx_h >= 0: self.combo_hero.setCurrentIndex(idx_h)
        
        # 触发一次显隐更新
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
        group.setChecked(False) # 默认不勾选，里面的控件是灰色的(不可点)
        group.toggled.connect(self.auto_save)
        
        form = QFormLayout()
        
        # A. 最高解锁等级
        spin_max = QSpinBox()
        spin_max.setRange(1, 10)
        spin_max.setValue(10)
        spin_max.setSuffix(" Lv")
        # [修改] 去掉上下按钮
        spin_max.setButtonSymbols(QAbstractSpinBox.NoButtons) 
        spin_max.valueChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_max_unlock_level"), spin_max)
        
        # B. 模式选择
        combo_mode = QComboBox()
        combo_mode.addItem(get_text("opt_mode_train_new"), "train")
        combo_mode.addItem(get_text("opt_mode_promote"), "promote")
        combo_mode.currentIndexChanged.connect(self.auto_save)
        form.addRow(get_text("cfg_train_mode"), combo_mode)
        
        # C. 操作等级
        lbl_target = QLabel(get_text("cfg_operate_level"))
        spin_target = QSpinBox()
        spin_target.setRange(1, 10)
        spin_target.setValue(9) # 默认设为9
        spin_target.setSuffix(" Lv")
        # [修改] 去掉上下按钮
        spin_target.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin_target.valueChanged.connect(self.auto_save)
        form.addRow(lbl_target, spin_target)
        
        group.setLayout(form)
        self.layout.addWidget(group)
        
        controls = {
            "group": group,
            "spin_max": spin_max,
            "combo_mode": combo_mode,
            "lbl_target": lbl_target,
            "spin_target": spin_target
        }
        self.troop_controls[prefix] = controls

        # 联动逻辑
        combo_mode.currentIndexChanged.connect(lambda idx, c=controls: self._on_mode_changed(c))
        spin_max.valueChanged.connect(lambda val, c=controls: self._on_max_level_changed(c))

    def _create_time_section(self):
        group = QGroupBox(get_text("lbl_time_settings"))
        hbox = QHBoxLayout()
        self.spin_h = QSpinBox()
        self.spin_h.setRange(0, 24)
        self.spin_h.setSuffix(" h")
        self.spin_h.setButtonSymbols(QAbstractSpinBox.NoButtons) # [修改]
        self.spin_h.valueChanged.connect(self.auto_save)
        
        self.spin_m = QSpinBox()
        self.spin_m.setRange(0, 59)
        self.spin_m.setSuffix(" m")
        self.spin_m.setButtonSymbols(QAbstractSpinBox.NoButtons) # [修改]
        self.spin_m.valueChanged.connect(self.auto_save)
        
        hbox.addWidget(QLabel(get_text("cfg_train_time_h")))
        hbox.addWidget(self.spin_h)
        hbox.addWidget(QLabel(get_text("cfg_train_time_m")))
        hbox.addWidget(self.spin_m)
        group.setLayout(hbox)
        self.layout.addWidget(group)

    def _on_mode_changed(self, controls):
        mode = controls["combo_mode"].currentData()
        max_lv = controls["spin_max"].value()
        spin_target = controls["spin_target"]
        lbl_target = controls["lbl_target"]

        spin_target.blockSignals(True)
        
        # 建议值：始终是 max_lv - 1 (至少是1)
        suggested_val = max(1, max_lv - 1)

        if mode == "train":
            lbl_target.setText(get_text("cfg_target_level_label", "目标等级"))
            spin_target.setMaximum(max_lv)
            # [修改] 训练新兵也默认为次顶级 (方便后续晋升活动)
            spin_target.setValue(suggested_val)
        else:
            lbl_target.setText(get_text("cfg_promote_from_label", "晋升来源"))
            # 晋升来源上限必须 < max_lv
            limit = max(1, max_lv - 1)
            spin_target.setMaximum(limit)
            spin_target.setValue(limit) # 也是次顶级
            
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
            
            # 手动刷新标签
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
        
        if name == "BeastTask":
            return BeastTaskConfigWidget(task_class)
            
        if name == "RallyTask":
            return RallyTaskConfigWidget(task_class)
            
        if name == "WolfTask":
            return WolfTaskConfigWidget(task_class)

        if name == "IntelTask":
            return IntelTaskConfigWidget(task_class)
        
        if name == "AllianceHelpTask":
            return AllianceHelpConfigWidget(task_class)
        
        if name == "MailTask":
             return MailTaskConfigWidget(task_class)
        
        if name == "StaminaControlTask":
            return StaminaControlConfigWidget(task_class)
        
        if name == "TroopTrainingTask":
            return TroopTrainingConfigWidget(task_class)
            
        # 默认返回基类（只有一个开关）
        return BaseTaskConfigWidget(task_class)
