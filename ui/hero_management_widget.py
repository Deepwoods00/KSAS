# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, 
    QSpinBox, QLabel, QGridLayout, QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from game.hero_manager import HeroManager
from i18n.i18n import get_text

class CollapsibleBox(QWidget):
    """自定义折叠控件"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False) # 默认收起
        self.toggle_button.setStyleSheet("text-align: left; font-weight: bold; padding: 5px;")
        self.toggle_button.toggled.connect(self.on_toggled)

        self.content_area = QWidget()
        self.content_area.setVisible(False) # 默认隐藏
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

    def on_toggled(self, checked):
        self.content_area.setVisible(checked)
        arrow = "▼" if checked else "▶"
        self.toggle_button.setText(f"{arrow} {self.toggle_button.text()[2:]}")

    def set_content_layout(self, layout):
        self.content_area.setLayout(layout)
        
    def set_title(self, title):
        arrow = "▼" if self.toggle_button.isChecked() else "▶"
        self.toggle_button.setText(f"{arrow} {title}")

class HeroManagementWidget(QWidget):
    """
    英雄管理组件
    使用折叠菜单展示英雄列表，允许用户配置拥有状态和队列信息。
    """

    # 英雄分组定义 (用于 UI 展示)
    HERO_GROUPS = {
        "Gen 4": ["rosa", "alcar", "margot"],
        "Gen 3": ["jaeger", "eric", "petra"],
        "Gen 2": ["hilde", "zoe", "marlin"],
        "Gen 1": ["jabel", "amadeus", "helga", "saul"],
        "SR (Epic)": ["amane", "yeonwoo", "fahd", "chenko", "gordon", "diana", "howard", "quinn"],
        "R (Rare)": ["olive", "edwin", "seth", "forrest"]
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hero_manager = None
        self.widgets = {} # {hero_name: {"chk": QCheckBox, "spin": QSpinBox}}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 使用自定义折叠控件包裹整个内容
        self.main_collapsible = CollapsibleBox(f"▶ {get_text('title_hero_management', '英雄状态管理')}")
        layout.addWidget(self.main_collapsible)

        # 内部布局 (放入 ScrollArea)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        inner_widget = QWidget()
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        
        # 动态创建分组 (使用 CollapsibleBox 替代 QToolBox)
        for group_name, heroes in self.HERO_GROUPS.items():
            # 创建分组折叠框
            group_box = CollapsibleBox(f"▶ {group_name}")
            
            # 创建分组内容页面
            page_layout = self.create_group_page_layout(heroes)
            group_box.set_content_layout(page_layout)
            
            inner_layout.addWidget(group_box)

        # 添加弹簧，确保内容靠上
        inner_layout.addStretch()
        
        scroll_area.setWidget(inner_widget)
        
        # 创建一个包装布局给 main_collapsible
        wrapper_layout = QVBoxLayout()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        # 设置最小高度，避免展开时太小
        scroll_area.setMinimumHeight(200)
        wrapper_layout.addWidget(scroll_area)
        
        self.main_collapsible.set_content_layout(wrapper_layout)

    def create_group_page_layout(self, heroes):
        """创建单个分组页面的布局"""
        # 使用 QWidget 包裹内容，以便放入 ScrollArea (如果需要) 或者直接作为布局
        # 这里直接返回布局，由 CollapsibleBox 的 content_area 使用
        
        # 为了美观，我们在每个分组里也加一个 ScrollArea，或者直接用 Grid
        # 考虑到英雄数量不多，直接用 Grid 即可。如果英雄很多，可以考虑 ScrollArea。
        # 这里为了保持一致性，我们还是用一个 Widget 包裹 Grid
        
        content_widget = QWidget()
        grid = QGridLayout(content_widget)
        grid.setColumnStretch(1, 1) # 让中间空白区域伸缩
        grid.setContentsMargins(10, 5, 10, 5) # 增加一点内边距

        # 表头
        lbl_name = QLabel(get_text("lbl_hero_name", "英雄"))
        lbl_name.setStyleSheet("font-weight: bold;")
        grid.addWidget(lbl_name, 0, 0)
        
        lbl_owned = QLabel(get_text("lbl_hero_owned", "拥有"))
        lbl_owned.setStyleSheet("font-weight: bold;")
        grid.addWidget(lbl_owned, 0, 2)
        
        lbl_status = QLabel(get_text("lbl_hero_queue", "状态"))
        lbl_status.setStyleSheet("font-weight: bold;")
        grid.addWidget(lbl_status, 0, 3)

        row = 1
        for hero_name in heroes:
            # 1. 英雄名称 (支持中文)
            hero_key = f"hero_{hero_name}"
            display_name = get_text(hero_key, hero_name.capitalize())
            lbl_name = QLabel(display_name)
            grid.addWidget(lbl_name, row, 0)

            # 2. 拥有状态 (CheckBox)
            chk_owned = QCheckBox()
            chk_owned.stateChanged.connect(lambda state, h=hero_name: self.on_owned_changed(h, state))
            grid.addWidget(chk_owned, row, 2, alignment=Qt.AlignCenter)

            # 3. 状态信息 (可点击切换的 Button 或 Label)
            # 这里为了简化操作，使用 QPushButton，点击切换 忙碌/空闲
            btn_status = QPushButton(get_text("val_idle", "空闲"))
            btn_status.setCheckable(True) # 选中表示忙碌
            btn_status.setFixedWidth(60)
            btn_status.clicked.connect(lambda checked, h=hero_name: self.on_status_changed(h, checked))
            grid.addWidget(btn_status, row, 3)

            # 存储控件引用以便后续更新
            self.widgets[hero_name] = {
                "chk": chk_owned,
                "btn_status": btn_status
            }
            row += 1

        # 布局本身
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content_widget)
        
        return layout

    def set_manager(self, manager: HeroManager):
        """设置 HeroManager 实例并刷新 UI"""
        self.hero_manager = manager
        self.refresh_ui()

    def refresh_ui(self):
        """从 Manager 读取数据更新 UI"""
        if not self.hero_manager:
            return

        # 临时断开信号，防止循环触发
        self.block_signals(True)

        for hero_name, controls in self.widgets.items():
            info = self.hero_manager.get_hero_info(hero_name)
            
            # 更新 CheckBox
            is_owned = info.get("owned", False)
            controls["chk"].setChecked(is_owned)
            
            # 更新状态 Button
            state = info.get("state", "idle")
            is_busy = (state == "busy")
            
            btn = controls["btn_status"]
            btn.setChecked(is_busy)
            self.update_status_btn_style(btn, is_busy)
            
            # 如果未拥有，禁用状态切换
            btn.setEnabled(is_owned)

        self.block_signals(False)

    def update_status_btn_style(self, btn, is_busy):
        if is_busy:
            btn.setText(get_text("val_busy", "忙碌"))
            btn.setStyleSheet("background-color: #ffcccc; color: red; border: 1px solid red;")
        else:
            btn.setText(get_text("val_idle", "空闲"))
            btn.setStyleSheet("color: green;")

    def block_signals(self, block):
        """批量屏蔽/恢复信号"""
        for controls in self.widgets.values():
            controls["chk"].blockSignals(block)
            controls["btn_status"].blockSignals(block)

    def on_owned_changed(self, hero_name, state):
        """处理拥有状态变更"""
        if not self.hero_manager: return
        
        is_owned = (state == Qt.Checked.value)
        self.hero_manager.update_hero_status(hero_name, owned=is_owned)
        
        # 联动：如果取消拥有，禁用状态按钮并重置为空闲
        controls = self.widgets.get(hero_name)
        if controls:
            btn = controls["btn_status"]
            btn.setEnabled(is_owned)
            if not is_owned:
                self.hero_manager.update_hero_status(hero_name, state="idle")
                btn.setChecked(False)
                self.update_status_btn_style(btn, False)

    def on_status_changed(self, hero_name, checked):
        """处理状态变更 (点击按钮)"""
        if not self.hero_manager: return
        
        new_state = "busy" if checked else "idle"
        self.hero_manager.update_hero_status(hero_name, state=new_state)
        
        # 更新按钮样式
        controls = self.widgets.get(hero_name)
        if controls:
            self.update_status_btn_style(controls["btn_status"], checked)
