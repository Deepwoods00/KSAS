# -*- coding: utf-8 -*-
import sys
import os
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QListWidgetItem, QMessageBox, QWidget,
    QSystemTrayIcon, QMenu, QStyle, QInputDialog, QGridLayout,
    QGroupBox, QLabel, QVBoxLayout
)
from PySide6.QtCore import (
    QTimer, Slot, Signal, QFile, QIODevice, QObject, Qt, QEvent, QThread
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QColor, QIcon, QAction, QCursor, QTextCursor

from instance_manager import InstanceManager
from task_registry import get_all_tasks
from ui.task_widgets import TaskWidgetFactory
from ui.settings_dialog import SettingsDialog
from ui.add_instance_dialog import AddInstanceDialog
from ui.edit_instance_dialog import EditInstanceDialog
from config import global_config
from i18n.i18n import get_text
from ui.hero_management_widget import HeroManagementWidget
from game.hero_manager import HeroManager
from ui.collapsible_box import CollapsibleBox

# ============================================================================
# 💓 KeyAuth 心跳线程 (定义在主逻辑类之前或之后均可，这里放在前面方便管理)
# ============================================================================
class KeyAuthHeartbeatThread(QThread):
    """
    KeyAuth 心跳保活线程 (带冗余重试机制)
    策略:
    1. 正常状态：每 30 分钟检测一次。
    2. 失败状态：进入重试模式，每 3 分钟检测一次。
    3. 判定死亡：连续 3 次失败后，发送死亡信号。
    """
    sig_auth_failed = Signal(str)  # 彻底失败信号

    def __init__(self, keyauth_app):
        super().__init__()
        self.api = keyauth_app
        self._is_running = True
        self.failed_attempts = 0 # 当前连续失败次数
        
        # 配置
        self.INTERVAL_NORMAL = 30 * 60  # 正常间隔 30分钟
        self.INTERVAL_RETRY = 3 * 60    # 重试间隔 3分钟
        self.MAX_RETRIES = 3            # 最大重试次数

    def run(self):
        # 刚启动时，先等待一个周期再检查（因为登录时已经检查过了）
        self.smart_sleep(self.INTERVAL_NORMAL)

        while self._is_running:
            try:
                # 执行检测
                # print(f"[Heartbeat] Checking... (Failures: {self.failed_attempts})")
                is_valid = self.api.check()
                
                if is_valid:
                    # 成功：重置计数器，等待 30 分钟
                    if self.failed_attempts > 0:
                        print("[Heartbeat] Connection restored.")
                    self.failed_attempts = 0
                    self.smart_sleep(self.INTERVAL_NORMAL)
                else:
                    # 失败：计数+1
                    self.failed_attempts += 1
                    print(f"[Heartbeat] Check failed ({self.failed_attempts}/{self.MAX_RETRIES})")
                    
                    if self.failed_attempts >= self.MAX_RETRIES:
                        # 超过最大重试次数，发送死亡信号，结束循环
                        self.sig_auth_failed.emit(f"Heartbeat failed {self.MAX_RETRIES} times continuously.")
                        break
                    else:
                        # 还没死透，等待 3 分钟重试
                        self.smart_sleep(self.INTERVAL_RETRY)
                        
            except Exception as e:
                # 网络异常也算作失败
                self.failed_attempts += 1
                print(f"[Heartbeat] Exception: {e}")
                
                if self.failed_attempts >= self.MAX_RETRIES:
                    self.sig_auth_failed.emit(f"Network exception: {str(e)}")
                    break
                else:
                    self.smart_sleep(self.INTERVAL_RETRY)

    def smart_sleep(self, seconds):
        """
        分段休眠，确保程序关闭时线程能迅速响应退出，而不是傻等30分钟
        """
        for _ in range(seconds):
            if not self._is_running:
                break
            time.sleep(1)

    def stop(self):
        self._is_running = False
        self.wait()


# ============================================================================
# 🖥️ 主窗口逻辑
# ============================================================================
class MainWindowLogic(QObject):
    def __init__(self, keyauth_app=None):
        print(">>> 正在初始化 MainWindowLogic，参数:", keyauth_app) # 👈 加这句测试
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
        
        # 3.5 重构侧边栏按钮布局 (2x2)
        self.rearrange_sidebar_buttons()

        # 4. 连接信号
        self.ui.list_instances.itemClicked.connect(self.on_instance_selected)
        self.ui.btn_add_instance.clicked.connect(self.on_add_instance)
        self.ui.btn_refresh_adb.clicked.connect(self.on_refresh_adb)
        self.ui.btn_toggle_running.clicked.connect(self.on_toggle_running)
        self.ui.btn_global_settings.clicked.connect(self.on_global_settings)
        self.ui.btn_minimize.clicked.connect(self.minimize_to_tray)
        
        # 5. 初始化右键菜单
        self.setup_list_context_menus()
        self.setup_sidebar_context_menu()
        
        # 6. 初始化界面
        self.refresh_instances()
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_welcome)
        
        # 7. 启动定时器刷新状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_ui_status)
        self.status_timer.start(1000) 

        # 8. 安装事件过滤器 (用于监听体力条双击)
        self.ui.installEventFilter(self)
        # 👇 【关键】给体力条和它的文字标签也安装过滤器，确保点哪里都能触发
        self.ui.progress_stamina.installEventFilter(self)
        self.ui.label_stamina_val.installEventFilter(self)

        # 8.5 动态添加 Stats 页面的控件
        self.setup_stats_page()

        # 9. 应用初始翻译
        self.apply_translations()

        # 10. 启动 KeyAuth 心跳线程
        self.keyauth_thread = None
        if keyauth_app:
            self.start_heartbeat(keyauth_app)

    # ------------------------------------------------------------------------
    # 💓 心跳相关逻辑
    # ------------------------------------------------------------------------
    def start_heartbeat(self, keyauth_app):
        self.keyauth_thread = KeyAuthHeartbeatThread(keyauth_app)
        # 连接到新的紧急处理槽函数
        self.keyauth_thread.sig_auth_failed.connect(self.on_auth_failed_emergency)
        self.keyauth_thread.start()
        print("[System] Security heartbeat started (Interval: 30m, Redundancy: 3x3m).")

    def on_auth_failed_emergency(self, reason):
        """
        当心跳彻底失败（重试3次后）触发的紧急处理逻辑
        """
        print(f"[Security] EMERGENCY STOP: {reason}")
        
        # A. 停止所有运行中的实例
        running_count = 0
        all_schedulers = self.manager.schedulers
        
        for instance_id, sched in all_schedulers.items():
            if sched.isRunning():
                # 强制停止调度器
                sched.stop_scheduler()
                running_count += 1
                
                # 在对应实例的日志里写一句
                store = self.manager.get_store(instance_id)
                if store:
                    store.push_log("🛑 授权验证失败，强制停止任务！", "ERROR")

        # B. 更新 UI 状态 (调用现有的 update_ui_status 来刷新按钮状态)
        self.update_ui_status()
        
        # C. 禁用核心按钮，防止用户再次点击启动
        self.ui.btn_toggle_running.setEnabled(False)
        self.ui.btn_toggle_running.setText("授权失效")
        self.ui.btn_toggle_running.setStyleSheet("background-color: gray; color: white;")
        
        # D. 弹出对话框报错 (保持窗口开启)
        QMessageBox.critical(
            self.ui, 
            "Authorization Failed", 
            f"安全检测失败，已强制停止所有任务。\n\n原因: {reason}\n\n请检查网络连接或重启软件。"
        )

    # ------------------------------------------------------------------------
    # 🧩 界面布局与初始化
    # ------------------------------------------------------------------------
    def setup_stats_page(self):
        """在 Stats 页面动态添加控件"""
        # 查找 group_stamina 的父 Widget
        parent_widget = self.ui.group_stamina.parent()
        layout = parent_widget.layout()
        
        if not layout:
            layout = QVBoxLayout(parent_widget)
            
        # 创建一个新的 Widget 用于显示侧边栏信息 (不再使用 GroupBox)
        self.group_sidebar = QWidget(parent_widget)
        self.group_sidebar.setObjectName("group_sidebar")
        vbox = QVBoxLayout(self.group_sidebar)
        vbox.setContentsMargins(0, 10, 0, 10) # 增加上下间距
        
        # 创建 Label
        self.label_idle_queues_title = QLabel(self.group_sidebar)
        self.label_idle_queues_val = QLabel("?", self.group_sidebar)
        self.label_idle_queues_val.setStyleSheet("font-weight: bold; color: green; font-size: 12pt;")
        
        # 使用 Grid Layout
        hbox = QGridLayout()
        hbox.addWidget(self.label_idle_queues_title, 0, 0)
        hbox.addWidget(self.label_idle_queues_val, 0, 1)
        hbox.setColumnStretch(1, 1)
        
        vbox.addLayout(hbox)
        
        # 添加到主布局 (在 group_stamina 后面)
        layout.addWidget(self.group_sidebar)

        # 添加英雄管理组件
        self.hero_widget = HeroManagementWidget(parent_widget)
        layout.addWidget(self.hero_widget)

        # 添加弹簧，确保内容靠上
        layout.addStretch()

    def apply_translations(self):
        """应用当前语言的翻译"""
        # Sidebar
        self.ui.btn_add_instance.setText(get_text("btn_add_instance"))
        self.ui.btn_add_instance.setToolTip(get_text("btn_add_instance"))
        self.ui.btn_refresh_adb.setText(get_text("btn_refresh_adb"))
        self.ui.btn_global_settings.setText(get_text("btn_global_settings"))
        
        # Welcome
        self.ui.label_welcome.setText(get_text("lbl_welcome"))
        
        # Header
        self.update_ui_status() # 状态文本会在 update_ui_status 里更新
        
        # Tabs
        self.ui.tabWidget.setTabText(0, get_text("tab_tasks"))
        self.ui.tabWidget.setTabText(1, get_text("tab_logs"))
        self.ui.tabWidget.setTabText(2, get_text("tab_stats"))
        
        # Stats Group
        if hasattr(self.ui, 'group_stamina'):
            self.ui.group_stamina.setTitle(get_text("group_stamina"))
            
        if hasattr(self, 'group_sidebar'):
            self.label_idle_queues_title.setText(get_text("lbl_idle_queues"))

        # Task List Titles
        if hasattr(self.ui, 'lbl_running_title'):
            self.ui.lbl_running_title.setText(get_text("lbl_running_title"))
        if hasattr(self.ui, 'lbl_queue_title'):
            self.ui.lbl_queue_title.setText(get_text("lbl_queue_title"))
        if hasattr(self.ui, 'lbl_waiting_title'):
            self.ui.lbl_waiting_title.setText(get_text("lbl_waiting_title"))

    def show(self):
        self.ui.show()

    def minimize_to_tray(self):
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
        self.tray_icon = QSystemTrayIcon(self.ui)
        icon_path = os.path.join("assets", "logo.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.tray_icon.setIcon(icon)
            self.ui.setWindowIcon(icon)
            if hasattr(self.ui, 'label_logo'):
                pixmap = QPixmap(icon_path)
                self.ui.label_logo.setPixmap(pixmap.scaled(
                    self.ui.label_logo.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                ))
                self.ui.label_logo.setText("")
        else:
            self.tray_icon.setIcon(self.ui.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        action_show = QAction(get_text("显示主界面"), self.ui) 
        action_show.triggered.connect(self.show_window)
        tray_menu.addAction(action_show)
        action_quit = QAction(get_text("退出程序"), self.ui) 
        action_quit.triggered.connect(self.quit_app)
        tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def rearrange_sidebar_buttons(self):
        """将侧边栏底部的4个按钮改为 2x2 网格布局"""
        # 1. 获取容器和旧布局
        container = self.ui.sidebar_tools
        old_layout = container.layout()
        
        # 2. 获取按钮对象 (它们已经在 ui 对象里了)
        btn_add = self.ui.btn_add_instance
        btn_refresh = self.ui.btn_refresh_adb
        btn_settings = self.ui.btn_global_settings
        btn_minimize = self.ui.btn_minimize
        
        # 3. 创建新布局
        new_layout = QGridLayout()
        new_layout.setSpacing(5)
        new_layout.setContentsMargins(5, 5, 5, 5)
        
        # 4. 添加按钮 (Row, Col)
        # 第一行: 添加 | 刷新
        new_layout.addWidget(btn_add, 0, 0)
        new_layout.addWidget(btn_refresh, 0, 1)
        # 第二行: 设置 | 最小化
        new_layout.addWidget(btn_settings, 1, 0)
        new_layout.addWidget(btn_minimize, 1, 1)
        
        # 5. 替换布局
        QWidget().setLayout(old_layout) # 把旧布局的所有权转移给一个临时对象，从而销毁它
        container.setLayout(new_layout)

    # ===========================================
    # 🖱️ 事件过滤器 (处理双击事件等)
    # ===========================================
    def eventFilter(self, obj, event):
        # 1. 拦截关闭事件 -> 最小化
        if obj == self.ui and event.type() == QEvent.Close:
            if global_config.get("close_to_tray", False):
                event.ignore()
                self.ui.hide()
                self.tray_icon.showMessage("KSAS 已隐藏", "点击托盘图标可恢复。", QSystemTrayIcon.Information, 2000)
                return True
            else:
                self.quit_app()
                return False
        
        # 2. 拦截体力条的双击事件 -> 修改体力
        if event.type() == QEvent.MouseButtonDblClick:
            if obj == self.ui.progress_stamina or obj == self.ui.label_stamina_val:
                self.do_edit_stamina()
                return True

        return super().eventFilter(obj, event)

    def do_edit_stamina(self):
        """弹出对话框修改体力"""
        if not self.current_instance_id: return
        
        store = self.manager.get_store(self.current_instance_id)
        current_val = store.get_stat("stamina", 0)
        
        val, ok = QInputDialog.getInt(
            self.ui, 
            get_text("group_stamina"),
            get_text("msg_input_stamina"),
            value=current_val,
            minValue=0, 
            maxValue=10000
        )
        
        if ok:
            store.set_stat("stamina", val)
            self.ui.text_log.append(f"<font color='#FF8C00'>[User] 手动更新体力: {val}</font>")
            # UI 刷新会由 update_ui_status 自动接管，不需要手动 setProgressBar

    def show_window(self):
        self.ui.showNormal()
        self.ui.activateWindow()

    def quit_app(self):
        self.tray_icon.hide()
        # 停止心跳线程
        if hasattr(self, 'keyauth_thread') and self.keyauth_thread:
            self.keyauth_thread.stop()
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
        
        store = self.manager.get_store(instance_id)
        try: store.sig_log_msg.disconnect()
        except: pass
        store.sig_log_msg.connect(self.append_log)

        # 初始化并刷新英雄管理组件
        if hasattr(self, 'hero_widget'):
            hero_mgr = HeroManager(store)
            self.hero_widget.set_manager(hero_mgr)
        
        self.ui.text_log.clear()
        log_path = os.path.join("data", instance_id, "log", "ksas.log") 
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-50:]
                    for line in lines:
                        self.ui.text_log.append(f"<span style='color:gray'>{line.strip()}</span>")
            except Exception as e:
                print(f"读取日志失败: {e}")
        self.update_ui_status()

    def append_log(self, level, full_msg):
        try:
            if "|||" in full_msg:
                sender_id, real_msg = full_msg.split("|||", 1)
            else:
                sender_id = "System"
                real_msg = full_msg
                
            if sender_id != self.current_instance_id:
                return
                
            color = "black"
            if "ERROR" in level: color = "red"
            elif "WARNING" in level: color = "#FF8C00"
            elif "DEBUG" in level: color = "gray"
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html = f'<span style="color:gray">[{time_str}]</span> <span style="color:{color}">{real_msg}</span>'
            
            doc = self.ui.text_log.document()
            while doc.blockCount() > 100:
                cursor = self.ui.text_log.textCursor()
                cursor.movePosition(QTextCursor.Start)
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()

            self.ui.text_log.append(html)
            self.ui.text_log.ensureCursorVisible()
            
        except Exception as e:
            print(f"Log Error: {e}")

    def load_task_configs(self, instance_id):
        layout = self.ui.scrollAreaWidgetContents.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.config_widgets = []
        
        store = self.manager.get_store(instance_id)
        task_classes = get_all_tasks()
        
        # 动态分类
        categories = {}
        
        # 默认分类映射 (作为后备)
        default_category_map = {
            "GeneralSettings": "General",
            "WolfTask": "Combat",
            "BeastTask": "Combat",
            "RallyTask": "Combat",
            "IntelTask": "Daily",
            "GatherTask": "Daily",
            "ShopTask": "Shop",
            "TestSidebarTask": "Other",
            "ExampleTask": "Other"
        }

        for task_cls in task_classes:
            # 1. 尝试从 config_schema 获取 menu
            menu = "Other"
            if hasattr(task_cls, 'config_schema'):
                for item in task_cls.config_schema:
                    if 'menu' in item:
                        menu = item['menu']
                        break
            
            # 2. 如果没找到，尝试使用默认映射
            if menu == "Other":
                menu = default_category_map.get(task_cls.__name__, "Other")
            
            if menu not in categories:
                categories[menu] = []
            categories[menu].append(task_cls)

        # 排序分类: General 总是第一，Other 总是最后，其他按字母顺序
        sorted_cats = sorted(categories.keys())
        if "General" in sorted_cats:
            sorted_cats.remove("General")
            sorted_cats.insert(0, "General")
        if "Other" in sorted_cats:
            sorted_cats.remove("Other")
            sorted_cats.append("Other")
        
        for cat_name in sorted_cats:
            tasks = categories[cat_name]
            if not tasks: continue
            
            # 获取翻译后的分类名称
            trans_key = f"cat_{cat_name.lower()}"
            display_name = get_text(trans_key)
            if display_name == trans_key:
                display_name = cat_name

            # 创建容器布局
            if cat_name == "General":
                # General 不折叠，直接添加
                container_layout = layout
            else:
                # 其他分类使用折叠框
                box = CollapsibleBox(title=display_name)
                layout.addWidget(box)
                
                # 折叠框的内容布局
                content_widget = QWidget()
                vbox = QVBoxLayout(content_widget)
                vbox.setContentsMargins(5, 5, 5, 5)
                box.setContentLayout(vbox)
                container_layout = vbox

                # 当分类折叠时，自动折叠所有子任务
                box.toggled_state.connect(lambda c, l=vbox: self.on_category_toggled(c, l))
            
            for task_cls in tasks:
                widget = TaskWidgetFactory.create_widget(task_cls)
                widget.load_from_store(store)
                container_layout.addWidget(widget)
                self.config_widgets.append(widget)
                widget.show()

        layout.addStretch()
        self.ui.scrollAreaWidgetContents.update()

    def on_category_toggled(self, checked, layout):
        """当分类折叠时，折叠其下的所有任务卡片"""
        if not checked: # Collapsed
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget() and hasattr(item.widget(), 'collapse'):
                    item.widget().collapse()

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
            self.ui.text_log.append(f"<font color='green'><b>>>> 调度器已启动 (Scheduler Started)</b></font>")
        else:
            sched.stop_scheduler()
            self.ui.text_log.append(f"<font color='red'><b>>>> 调度器正在停止...</b></font>")
        self.update_ui_status()

    def update_ui_status(self):
        if not self.current_instance_id:
            return
        
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched: return
        
        is_running = sched.isRunning()
        # 更新按钮状态（如果代码与按钮状态不一致时）
        if self.ui.btn_toggle_running.isChecked() != is_running:
            # 在紧急停止情况下，这里可能会把按钮重置为 unchecked，这符合预期
            self.ui.btn_toggle_running.setChecked(is_running)
            
        if is_running:
            self.ui.btn_toggle_running.setText(get_text("btn_stop"))
            self.ui.btn_toggle_running.setProperty("state", "running")
            self.ui.label_status_text.setText(get_text("lbl_status_running"))
            self.ui.label_status_icon.setText("🟢")
        else:
            # 如果是因为授权失败被禁用，文字会被 on_auth_failed_emergency 覆盖，这里需要保留
            if self.ui.btn_toggle_running.isEnabled():
                self.ui.btn_toggle_running.setText(get_text("btn_start"))
            
            self.ui.btn_toggle_running.setProperty("state", "stopped")
            self.ui.label_status_text.setText(get_text("lbl_status_idle"))
            self.ui.label_status_icon.setText("⚪")
        
        self.ui.btn_toggle_running.style().unpolish(self.ui.btn_toggle_running)
        self.ui.btn_toggle_running.style().polish(self.ui.btn_toggle_running)

        store = self.manager.get_store(self.current_instance_id)
        stamina = store.get_stat("stamina", 0)
        self.ui.progress_stamina.setMaximum(200)
        self.ui.progress_stamina.setValue(int(stamina))
        self.ui.progress_stamina.setTextVisible(False)
        self.ui.label_stamina_val.setText(f"{stamina} / 200")

        # 更新侧边栏统计
        idle_queues = store.get_stat("sidebar.idle_queues", "?")
        if hasattr(self, 'label_idle_queues_val'):
            self.label_idle_queues_val.setText(str(idle_queues))

        self.update_task_lists(sched)

    def update_task_lists(self, sched):
        self.ui.list_running.clear()
        self.ui.list_queue.clear()
        self.ui.list_waiting.clear()
        
        if not sched: return

        store = self.manager.get_store(self.current_instance_id)
        
        current_task_name = store.get_runtime("current_task", "Idle")
        is_running_logic = store.get_runtime("is_running", False)

        if is_running_logic and "休眠" not in current_task_name and "待机" not in current_task_name and "Idle" not in current_task_name:
             self.ui.list_running.addItem(f"{get_text('lbl_running_title')} {current_task_name}")
        elif is_running_logic:
             self.ui.list_running.addItem(f"{get_text('lbl_waiting_title')} {current_task_name}")
        
        now = datetime.now()
        queue_tasks = []
        waiting_tasks = []

        for task in sched.tasks:
            if not task.enabled:
                continue
            
            time_str = task.next_run.strftime("%H:%M:%S") if task.next_run.year > 2000 else "立即"
            
            if task.name == current_task_name and "休眠" not in current_task_name:
                continue

            if now >= task.next_run:
                queue_tasks.append((task, time_str))
            else:
                waiting_tasks.append((task, time_str))

        queue_tasks.sort(key=lambda x: x[0].priority)
        for task, t_str in queue_tasks:
            item = QListWidgetItem(f"[{task.priority}] {task.name}")
            item.setData(Qt.UserRole, task.name)
            self.ui.list_queue.addItem(item)

        waiting_tasks.sort(key=lambda x: x[0].next_run)
        for task, t_str in waiting_tasks:
            item = QListWidgetItem(f"{task.name}  ({t_str})")
            item.setData(Qt.UserRole, task.name)
            self.ui.list_waiting.addItem(item)

    def setup_list_context_menus(self):
        for lst in [self.ui.list_queue, self.ui.list_waiting]:
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(self.on_task_context_menu)

    def on_task_context_menu(self, pos):
        sender_list = self.sender()
        item = sender_list.itemAt(pos)
        if not item: return
        
        task_name = item.data(Qt.UserRole)
        menu = QMenu()
        action_run = QAction(f"{get_text('menu_run_now')} {task_name}", self.ui)
        action_run.triggered.connect(lambda: self.reset_task_next_run(task_name))
        menu.addAction(action_run)
        menu.exec(QCursor.pos())

    def reset_task_next_run(self, task_name):
        if not self.current_instance_id: return
        store = self.manager.get_store(self.current_instance_id)
        store.set_stat(f"tasks.{task_name}.next_run", "")
        self.ui.text_log.append(f"<font color='#1e90ff'>[User] 已强制插队任务: {task_name}</font>")
    
    def setup_sidebar_context_menu(self):
        self.ui.list_instances.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.list_instances.customContextMenuRequested.connect(self.on_sidebar_menu)

    def on_sidebar_menu(self, pos):
        item = self.ui.list_instances.itemAt(pos)
        if not item: return
        instance_id = item.data(Qt.UserRole)
        
        menu = QMenu()
        action_edit = QAction(get_text("menu_edit_info"), self.ui)
        action_edit.triggered.connect(lambda: self.do_edit_instance(instance_id))
        menu.addAction(action_edit)

        action_folder = QAction(get_text("menu_open_folder"), self.ui)
        action_folder.triggered.connect(lambda: self.do_open_folder(instance_id))
        menu.addAction(action_folder)
        
        menu.addSeparator()
        
        action_del = QAction(get_text("menu_delete"), self.ui)
        action_del.triggered.connect(lambda: self.do_delete_instance(instance_id))
        menu.addAction(action_del)
        menu.exec(QCursor.pos())

    def do_edit_instance(self, instance_id):
        store = self.manager.get_store(instance_id)
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        
        old_name = target['name'] if target else instance_id
        old_serial = store.get_cfg("meta.serial", "")
        old_diana = store.get_cfg("modules.general.diana_level", 0)
        old_march = store.get_cfg("modules.general.total_march_slots", 5)
        
        dialog = EditInstanceDialog(
            self.ui,
            current_name=old_name,
            current_serial=old_serial,
            current_diana=old_diana,
            current_march_slots=old_march
        )
        
        if dialog.exec():
            new_name, new_serial, new_diana, new_march = dialog.get_data()
            if not new_name or not new_serial:
                QMessageBox.warning(self.ui, get_text("msg_error"), get_text("msg_input_invalid"))
                return

            self.manager.update_instance(
                instance_id,
                new_serial=new_serial,
                new_alias=new_name,
                new_diana_level=new_diana,
                new_march_slots=new_march
            )
            self.ui.text_log.append(f"<font color='blue'>[System] 实例信息已更新: {new_name} (Diana Lv.{new_diana}, March: {new_march})</font>")

    def do_delete_instance(self, instance_id):
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        name = target['name'] if target else instance_id

        reply = QMessageBox.question(
            self.ui, 
            get_text("msg_confirm_del"),
            get_text("msg_del_warn", name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            sched = self.manager.get_scheduler(instance_id)
            if sched and sched.isRunning():
                sched.stop_scheduler()
                
            self.manager.delete_instance(instance_id)
            
            if self.current_instance_id == instance_id:
                self.current_instance_id = None
                self.ui.stacked_pages.setCurrentIndex(0) 
            
            QMessageBox.information(self.ui, get_text("msg_success"), get_text("msg_success"))

    def do_open_folder(self, instance_id):
        store = self.manager.get_store(instance_id)
        if store:
            path = os.path.abspath(store.base_dir)
            os.startfile(path)

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
            name, serial, diana, march = dialog.get_data()
            if not name or not serial:
                QMessageBox.warning(self.ui, get_text("msg_error"), get_text("msg_input_invalid"))
                return
            
            success, msg = self.manager.create_instance(name, serial, diana, march)
            if success:
                QMessageBox.information(self.ui, get_text("msg_success"), f"Instance '{name}' created!")
            else:
                QMessageBox.critical(self.ui, get_text("msg_error"), f"Failed: {msg}")

    def on_refresh_adb(self):
        self.refresh_instances()
        self.ui.statusbar.showMessage("实例列表已刷新", 2000)

    def on_global_settings(self):
        dialog = SettingsDialog(self.ui)
        if dialog.exec():
            # 如果设置里改了语言，这里需要刷新界面
            self.apply_translations()