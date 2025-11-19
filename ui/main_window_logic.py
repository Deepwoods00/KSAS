# -*- coding: utf-8 -*-
import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QListWidgetItem, QMessageBox, QWidget, 
    QSystemTrayIcon, QMenu, QStyle
)
from PySide6.QtCore import QTimer, Slot, Signal, QFile, QIODevice, QObject, Qt, QEvent
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QColor, QIcon, QAction

from instance_manager import InstanceManager
from task_registry import get_all_tasks
from ui.task_widgets import TaskWidgetFactory
from ui.settings_dialog import SettingsDialog
from ui.add_instance_dialog import AddInstanceDialog
from config import global_config
from i18n import i18n

class MainWindowLogic(QObject):
    def __init__(self):
        super().__init__()
        
        # 1. 加载 UI
        self.ui = self.load_ui_file()
        
        # 2. 初始化核心组件
        self.manager = InstanceManager()
        self.current_instance_id = None
        self.config_widgets = [] 
        
        # 连接管理器信号
        self.manager.sig_instance_list_changed.connect(self.refresh_instances)
        
        # 3. 初始化托盘图标
        self.init_system_tray()

        # 4. 连接信号
        self.ui.list_instances.itemClicked.connect(self.on_instance_selected)
        self.ui.btn_add_instance.clicked.connect(self.on_add_instance)
        self.ui.btn_refresh_adb.clicked.connect(self.on_refresh_adb)
        self.ui.btn_toggle_running.clicked.connect(self.on_toggle_running)
        self.ui.btn_global_settings.clicked.connect(self.on_global_settings)
        self.ui.btn_minimize.clicked.connect(self.minimize_to_tray)
        
        # 5. 初始化界面
        self.refresh_instances()
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_welcome)
        
        # 6. 启动定时器刷新状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_ui_status)
        self.status_timer.start(1000)

        # 7. 安装事件过滤器
        self.ui.installEventFilter(self)

    def show(self):
        """显示主窗口"""
        self.ui.show()

    def minimize_to_tray(self):
        """最小化到托盘"""
        self.ui.hide()
        self.tray_icon.showMessage(
            "KSAS 已隐藏",
            "程序仍在后台运行，点击托盘图标可恢复。",
            QSystemTrayIcon.Information,
            2000
        )

    def load_ui_file(self):
        loader = QUiLoader()
        ui_path = os.path.join(os.path.dirname(__file__), "main_window.ui")
        ui_file = QFile(ui_path)
        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_path}: {ui_file.errorString()}")
            sys.exit(-1)
        ui = loader.load(ui_file)
        ui_file.close()
        if not ui:
            print(loader.errorString())
            sys.exit(-1)
        return ui

    def init_system_tray(self):
        """初始化系统托盘 & 设置应用图标"""
        self.tray_icon = QSystemTrayIcon(self.ui)
        
        # 尝试加载 Logo
        icon_path = os.path.join("assets", "logo.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.tray_icon.setIcon(icon)
            self.ui.setWindowIcon(icon)
            
            # 设置侧边栏 Logo
            if hasattr(self.ui, 'label_logo'):
                pixmap = QPixmap(icon_path)
                self.ui.label_logo.setPixmap(pixmap.scaled(
                    self.ui.label_logo.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                ))
                self.ui.label_logo.setText("") # 清除文字
        else:
            # Fallback: 使用标准图标
            self.tray_icon.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        # 托盘菜单
        tray_menu = QMenu()
        
        action_show = QAction("显示主界面", self.ui)
        action_show.triggered.connect(self.show_window)
        tray_menu.addAction(action_show)
        
        action_quit = QAction("退出程序", self.ui)
        action_quit.triggered.connect(self.quit_app)
        tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def eventFilter(self, obj, event):
        """事件过滤器：拦截主窗口关闭事件"""
        if obj == self.ui and event.type() == QEvent.Close:
            # 只有在配置开启时才最小化到托盘
            if global_config.get("close_to_tray", False):
                event.ignore()
                self.ui.hide()
                self.tray_icon.showMessage(
                    "KSAS 已隐藏",
                    "程序仍在后台运行，点击托盘图标可恢复。",
                    QSystemTrayIcon.Information,
                    2000
                )
                return True # 事件已处理
            else:
                # 正常关闭退出
                self.quit_app()
                return False
        return super().eventFilter(obj, event)

    def show_window(self):
        self.ui.showNormal()
        self.ui.activateWindow()

    def quit_app(self):
        self.tray_icon.hide()
        sys.exit(0)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.ui.isVisible():
                self.ui.hide()
            else:
                self.show_window()

    def refresh_instances(self):
        self.ui.list_instances.clear()
        instances = self.manager.get_all_instances()
        for inst in instances:
            item = QListWidgetItem()
            name = inst.get('alias') or inst.get('id')
            item.setText(name)
            item.setData(Qt.UserRole, inst['id'])
            self.ui.list_instances.addItem(item)

    def on_instance_selected(self, item):
        instance_id = item.data(Qt.UserRole)
        self.current_instance_id = instance_id
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_instance_detail)
        
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        if target:
            self.ui.label_instance_name.setText(target.get('alias', instance_id))
            
        self.load_task_configs(instance_id)
        self.update_ui_status()

    def load_task_configs(self, instance_id):
        layout = self.ui.scrollAreaWidgetContents.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.config_widgets = []
        
        store = self.manager.get_store(instance_id)
        task_classes = get_all_tasks()
        
        for task_cls in task_classes:
            widget = TaskWidgetFactory.create_widget(task_cls)
            widget.load_from_store(store)
            layout.addWidget(widget)
            self.config_widgets.append(widget)
            
        layout.addStretch()

    def save_current_configs(self):
        if not self.current_instance_id:
            return
        store = self.manager.get_store(self.current_instance_id)
        for widget in self.config_widgets:
            widget.save_to_store(store)

    def on_toggle_running(self):
        if not self.current_instance_id:
            return
        self.save_current_configs()
        
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched:
            return

        if self.ui.btn_toggle_running.isChecked():
            sched.start_scheduler()
            self.ui.text_log.append(f"<font color='green'>[System] Scheduler started.</font>")
        else:
            sched.stop_scheduler()
            self.ui.text_log.append(f"<font color='red'>[System] Scheduler stopping...</font>")
        self.update_ui_status()

    def update_ui_status(self):
        if not self.current_instance_id:
            return
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched:
            return
        is_running = sched.isRunning()
        
        if self.ui.btn_toggle_running.isChecked() != is_running:
            self.ui.btn_toggle_running.setChecked(is_running)
            
        if is_running:
            self.ui.btn_toggle_running.setText("⏹ 停止挂机")
            self.ui.btn_toggle_running.setStyleSheet("background-color: #c62828; color: white; border-color: #b71c1c;")
            self.ui.label_status_text.setText("Running")
            self.ui.label_status_icon.setText("🟢")
        else:
            self.ui.btn_toggle_running.setText("▶ 启动挂机")
            self.ui.btn_toggle_running.setStyleSheet("background-color: #2e7d32; color: white; border-color: #1b5e20;")
            self.ui.label_status_text.setText("Idle")
            self.ui.label_status_icon.setText("⚪")

        store = self.manager.get_store(self.current_instance_id)
        stamina = store.get_stat("stamina", 0)
        self.ui.progress_stamina.setValue(min(stamina, 200))
        self.ui.label_stamina_val.setText(str(stamina))
        
        resources = store.get_stat("resources", {})
        self.ui.val_food.setText(self._format_number(resources.get("food", 0)))
        self.ui.val_wood.setText(self._format_number(resources.get("wood", 0)))
        self.ui.val_stone.setText(self._format_number(resources.get("stone", 0)))
        self.ui.val_iron.setText(self._format_number(resources.get("iron", 0)))

    def _format_number(self, num):
        try:
            n = float(num)
        except (ValueError, TypeError):
            return "0"
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        else:
            return str(int(n))

    def on_add_instance(self):
        dialog = AddInstanceDialog(self.ui)
        if dialog.exec():
            name, serial = dialog.get_data()
            if not name or not serial:
                QMessageBox.warning(self.ui, "错误", "名称和 Serial 不能为空！")
                return
            
            success, msg = self.manager.create_instance(name, serial)
            if success:
                QMessageBox.information(self.ui, "成功", f"实例 '{name}' 创建成功！")
            else:
                QMessageBox.critical(self.ui, "失败", f"创建失败: {msg}")

    def on_refresh_adb(self):
        """刷新实例列表"""
        self.refresh_instances()
        self.ui.statusbar.showMessage("实例列表已刷新", 2000)

    def on_global_settings(self):
        dialog = SettingsDialog(self.ui)
        dialog.exec()
