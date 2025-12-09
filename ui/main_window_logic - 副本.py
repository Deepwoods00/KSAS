# -*- coding: utf-8 -*-
import sys
import os
import time
from datetime import datetime


from PySide6.QtWidgets import QMainWindow
from ui.ui_main_window import Ui_MainWindow
from PySide6.QtWidgets import (
    QMainWindow, QListWidgetItem, QMessageBox, QWidget,
    QSystemTrayIcon, QMenu, QStyle, QInputDialog, QGridLayout,
    QGroupBox, QLabel, QVBoxLayout, QHBoxLayout, QSplitter, QApplication
)
from PySide6.QtCore import (
    QTimer, Slot, Signal, QFile, QIODevice, QObject, Qt, QEvent, QThread
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QColor, QIcon, QAction, QCursor, QTextCursor
import threading

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
from ui.task_summary_widget import TaskSummaryWidget

# ============================================================================
# 💓 KeyAuth 心跳线程 (定义在主逻辑类之前或之后均可，这里放在前面方便管理)
# ============================================================================
class KeyAuthHeartbeatThread(QThread):
    """
    KeyAuth 心跳保活线程 (使用 threading.Event 实现优雅退出)
    """
    sig_auth_failed = Signal(str)

    def __init__(self, keyauth_app):
        super().__init__()
        self.setObjectName("KeyAuth_Thread") # 方便调试定位
        self.api = keyauth_app
        
        # 🟢 改动点 1：使用 Event 事件对象，而不是简单的 True/False
        # 默认为 False (红灯)，调用 set() 后变为 True (绿灯)
        self._exit_event = threading.Event()
        
        self.failed_attempts = 0
        self.INTERVAL_NORMAL = 30 * 60  # 30分钟
        self.INTERVAL_RETRY = 3 * 60    # 3分钟
        self.MAX_RETRIES = 3

    def stop(self):
        print("[Heartbeat] Stop signal received.")
        self._exit_event.set()
        
        # 1. 先尝试温柔等待 (最多等 2 秒)
        # 如果线程只是在 sleep，它会瞬间结束，wait 返回 True
        if not self.wait(2000): 
            # 2. 如果 2 秒后还没停 (说明卡在网络请求了)
            print("[Heartbeat] Thread stuck in network request. Forcing terminate.")
            self.terminate() # 🔪 强制杀死线程
            self.wait()

    def run(self):
        # 🟢 改动点 3：整个逻辑重写，删除了 smart_sleep
        
        # 1. 刚启动时，先等待一个周期再检查
        # wait(时间) 的意思是：在这里停 30分钟。
        # 如果期间 _exit_event 被 set() 了，它会立即苏醒并返回 True -> 此时直接 return 退出
        if self._exit_event.wait(self.INTERVAL_NORMAL):
            return 

        # 2. 进入循环，只要没收到退出信号就一直跑
        while not self._exit_event.is_set():
            try:
                # 执行网络请求 (可能会阻塞几秒，无法瞬间中断，但这是允许的)
                is_valid = self.api.check()
                
                # 请求回来后，再次检查一下是否要退出了
                if self._exit_event.is_set():
                    break

                if is_valid:
                    # --- 验证成功 ---
                    if self.failed_attempts > 0:
                        print("[Heartbeat] Connection restored.")
                    self.failed_attempts = 0
                    
                    # 等待 30 分钟 (可随时被中断)
                    if self._exit_event.wait(self.INTERVAL_NORMAL):
                        return 
                else:
                    # --- 验证失败 ---
                    self.failed_attempts += 1
                    print(f"[Heartbeat] Check failed ({self.failed_attempts}/{self.MAX_RETRIES})")
                    
                    if self.failed_attempts >= self.MAX_RETRIES:
                        self.sig_auth_failed.emit(f"Heartbeat failed {self.MAX_RETRIES} times.")
                        break # 彻底失败，退出循环
                    else:
                        # 等待 3 分钟重试 (可随时被中断)
                        if self._exit_event.wait(self.INTERVAL_RETRY):
                            return

            except Exception as e:
                # --- 网络异常 ---
                self.failed_attempts += 1
                print(f"[Heartbeat] Exception: {e}")
                
                if self.failed_attempts >= self.MAX_RETRIES:
                    self.sig_auth_failed.emit(f"Network exception: {str(e)}")
                    break
                else:
                    if self._exit_event.wait(self.INTERVAL_RETRY):
                        return
                        
        print("[Heartbeat] Thread loop finished.")


# ============================================================================
# 🖥️ 主窗口逻辑
# ============================================================================
class MainWindowLogic(QObject):
    def __init__(self, keyauth_app=None):
        print(">>> 正在初始化 MainWindowLogic，参数:", keyauth_app) # 👈 加这句测试
        super().__init__()
        
        # 1. 创建主窗口实体 (这是真正的窗口对象)
        self.main_window = QMainWindow()
        
        # 2. 实例化 UI 类 (这是存放所有按钮、标签的容器)
        self.ui = Ui_MainWindow()
        
        # 3. 将 UI 布局“安装”到主窗口上
        self.ui.setupUi(self.main_window)
        
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
        self.main_window.installEventFilter(self) 
        # 👇 【关键】给体力条和它的文字标签也安装过滤器，确保点哪里都能触发
        self.ui.progress_stamina.installEventFilter(self)
        self.ui.label_stamina_val.installEventFilter(self)

        # 8.5 动态添加 Stats 页面的控件
        self.setup_stats_page()

        # 8.6 初始化任务概览面板
        self.setup_task_summary_panel()

        # 9. 应用初始翻译
        self.apply_translations()

        # 10. 启动 KeyAuth 心跳线程
        self.keyauth_thread = None
        if keyauth_app:
            self.start_heartbeat(keyauth_app)

        self.ui.statusbar.setSizeGripEnabled(False)

        # 2. 设置状态栏默认样式：透明背景，深色文字 (融入 Tiffany 蓝)
        self.ui.statusbar.setStyleSheet("QStatusBar { background: #b2dfdb; color: #004D40; border: none; }")

        # 3. 连接信号 (监听消息消失)
        self.ui.statusbar.messageChanged.connect(self.on_statusbar_changed)

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
                    store.push_log(get_text("msg_heartbeat_fail", reason), "ERROR")

        # B. 更新 UI 状态 (调用现有的 update_ui_status 来刷新按钮状态)
        self.update_ui_status()
        
        # C. 禁用核心按钮，防止用户再次点击启动
        self.ui.btn_toggle_running.setEnabled(False)
        self.ui.btn_toggle_running.setText(get_text("btn_auth_invalid"))
        self.ui.btn_toggle_running.setStyleSheet("background-color: gray; color: white;")
        
        # D. 弹出对话框报错 (保持窗口开启)
        QMessageBox.critical(
            self.main_window,
            get_text("title_auth_failed"),
            get_text("msg_heartbeat_fail", reason)
        )

    # ------------------------------------------------------------------------
    # 🧩 界面布局与初始化
    # ------------------------------------------------------------------------
    def setup_task_summary_panel(self):
        """在任务配置页面添加右侧概览面板"""
        # 1. 获取 tab_tasks 的布局
        # 原有结构: tab_tasks -> verticalLayout_4 -> scrollArea
        # 我们需要改为: tab_tasks -> horizontalLayout -> QSplitter -> [scrollArea, summary_widget]
        
        # 获取 tab_tasks
        tab_tasks = self.ui.tab_tasks
        old_layout = tab_tasks.layout()
        
        # 获取 scrollArea (它现在在 old_layout 里)
        scroll_area = self.ui.scrollArea
        
        # 从旧布局中移除 scrollArea (但不要销毁)
        old_layout.removeWidget(scroll_area)
        
        # 创建新的水平布局
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建 QSplitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #00897B;
                width: 2px;
            }
        """)
        
        # 添加 ScrollArea (左侧)
        splitter.addWidget(scroll_area)
        
        # 创建并添加 TaskSummaryWidget (右侧)
        self.task_summary = TaskSummaryWidget(tab_tasks)
        splitter.addWidget(self.task_summary)
        
        # 设置初始比例 (3:1)
        # 注意：setSizes 接受的是像素值，这里给一个大概的比例即可，Qt 会自动调整
        splitter.setSizes([750, 250])
        
        # 防止窗口被完全折叠消失
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # 将 Splitter 添加到水平布局
        h_layout.addWidget(splitter)
        
        # 将新布局添加到旧布局中
        old_layout.addLayout(h_layout)

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
        self.ui.btn_minimize.setText(get_text("btn_minimize"))
        self.ui.btn_minimize.setToolTip(get_text("btn_minimize")) 
        
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

        # Task Summary
        if hasattr(self, 'task_summary'):
            self.task_summary.retranslate_ui()

        # Reload task configs to apply new translations to task names and categories
        if self.current_instance_id:
            self.load_task_configs(self.current_instance_id)

    def show(self):
        self.main_window.show()

    def minimize_to_tray(self):
        self.main_window.hide()
        self.tray_icon.showMessage(
            get_text("msg_app_hidden"),
            get_text("msg_click_restore"),
            QSystemTrayIcon.Information,
            2000
        )
    '''
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
    '''

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self.main_window)
        
        if getattr(sys, 'frozen', False):
            if hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            base_path = "."
            
        icon_path = os.path.join(base_path, "assets", "logo.png")
        
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.tray_icon.setIcon(icon)
            self.main_window.setWindowIcon(icon)
            if hasattr(self.ui, 'label_logo'):
                pixmap = QPixmap(icon_path)
                self.ui.label_logo.setPixmap(pixmap.scaled(
                    self.ui.label_logo.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                ))
                self.ui.label_logo.setText("")
        else:
            self.tray_icon.setIcon(self.main_window.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()
        action_show = QAction(get_text("msg_show_ui"), self.main_window)
        action_show.triggered.connect(self.show_window)
        tray_menu.addAction(action_show)
        action_quit = QAction(get_text("msg_quit_app"), self.main_window)
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
        if obj == self.main_window and event.type() == QEvent.Close:
            if global_config.get("close_to_tray", False):
                event.ignore()
                self.main_window.hide()
                self.tray_icon.showMessage(get_text("msg_app_hidden"), get_text("msg_click_restore"), QSystemTrayIcon.Information, 2000)
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
            self.main_window,
            get_text("group_stamina"),
            get_text("msg_input_stamina"),
            value=current_val,
            minValue=0, 
            maxValue=10000
        )
        
        if ok:
            store.set_stat("stamina", val)
            self.ui.text_log.append(f"<font color='#FF8C00'>{get_text('msg_manual_stamina', val)}</font>")
            # UI 刷新会由 update_ui_status 自动接管，不需要手动 setProgressBar

    def show_window(self):
        self.main_window.showNormal()
        self.main_window.activateWindow()

    def quit_app(self):
        self.tray_icon.hide()
        # 停止心跳线程
        if hasattr(self, 'keyauth_thread') and self.keyauth_thread:
            if self.keyauth_thread.isRunning():
                print("[System] Stopping KeyAuth thread...")
                self.keyauth_thread.stop()
                # wait() 会阻塞主线程直到子线程完全结束，避免“尸骨未寒”就退出
                self.keyauth_thread.wait() 
        if hasattr(self, 'manager'):
            for instance_id, sched in self.manager.schedulers.items():
                if sched.isRunning():
                    print(f"[System] Stopping scheduler for {instance_id}...")
                    sched.stop_scheduler()
                    # 同样，这里已经在 stop_scheduler 内部调用了 wait()，所以不需要再写
                    # 但为了双重保险，可以再加一个带超时的 wait
                    sched.wait(2000)
        print("[System] All threads stopped. Quitting Qt loop.")
        QApplication.instance().quit()
        # sys.exit(0) # 不要在这里强制退出，否则在 eventFilter 里会报错

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.main_window.isVisible():
                self.main_window.hide()
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


        try: store.sig_log_msg.disconnect(self.append_log)
        except: pass
        store.sig_log_msg.connect(self.append_log)

        # 2. 连接配置变更信号 (实现状态栏提示)
        try: store.sig_config_changed.disconnect(self.show_config_saved_msg)
        except: pass
        store.sig_config_changed.connect(self.show_config_saved_msg)

        # 初始化并刷新英雄管理组件
        if hasattr(self, 'hero_widget'):
            hero_mgr = HeroManager(store)
            self.hero_widget.set_manager(hero_mgr)
        
        self.ui.text_log.clear()
        log_path = os.path.join("data", instance_id, "log", "ksas.log") 
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    # 读取最后 50 行
                    lines = f.readlines()[-50:]
                    for line in lines:
                        line = line.strip()
                        if not line: continue
                        
                        # 1. 计算颜色
                        color = self._get_log_color(line)
                        
                        # 2. 格式化 (如果想让时间戳保持黑色，可以尝试简单的分割，这里简单起见整行着色)
                        # 如果需要时间戳黑色，可以将 line 分割，但这取决于你的日志格式
                        # 这里演示整行着色，简单有效
                        html = f"<span style='color:{color}'>{line}</span>"
                        
                        self.ui.text_log.append(html)
            except Exception as e:
                print(f"读取日志失败: {e}")
        self.update_ui_status()


    def _get_log_color(self, text):
        """
        根据日志内容判断应该显示的颜色
        """
        text_upper = text.upper()
        text_lower = text.lower()
        
        # 1. 优先判断级别
        if "ERROR" in text_upper:
            return "red"
        elif "WARNING" in text_upper:
            return "#FF8C00" # Orange
            
        # 2. 关键词判断 (INFO 级别下的语义着色)
        if any(k in text_lower for k in ["start", "启动", "开始"]):
            return "#008000" # Green
        elif any(k in text_lower for k in ["stop", "停止", "结束"]):
            return "#B22222" # FireBrick
        elif any(k in text_lower for k in ["sleep", "wait", "休眠", "等待"]):
            return "#4682B4" # SteelBlue
        elif any(k in text_lower for k in ["recover", "stamina", "体力"]):
            return "#20B2AA" # LightSeaGreen
        elif "success" in text_lower or "成功" in text_lower:
            return "#008000" # Green
        
        # 3. 默认黑色
        return "black"


    def append_log(self, level, full_msg):
        try:
            if "|||" in full_msg:
                sender_id, real_msg = full_msg.split("|||", 1)
            else:
                sender_id = "System"
                real_msg = full_msg
                
            if sender_id != self.current_instance_id:
                return
            

            check_str = f"{level} {real_msg}"
            color = self._get_log_color(check_str)
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html = f'<span style="color:black">[{time_str}]</span> <span style="color:{color}">{real_msg}</span>'
            
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

    def show_config_saved_msg(self, key, value):
        """
        当配置发生变化时，在状态栏显示提示
        """
        # 为了美观，去掉 "modules." 前缀，只显示后面的关键部分
        short_key = key.replace("modules.", "")
        msg = get_text("msg_config_saved", short_key, value)
        
        # 提示时：深青色背景，白色文字，醒目
        self.ui.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #00695C; 
                color: white; 
                font-weight: bold; 
                font-size: 11pt;
            }
        """)
        
        self.ui.statusbar.showMessage(msg, 3000)
        
        # 同时添加到日志窗口 (紫色)
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:black">[{time_str}]</span> <span style="color:#800080">{msg}</span>'
        self.ui.text_log.append(html)
        self.ui.text_log.ensureCursorVisible()

    def on_statusbar_changed(self, message):
        """
        状态栏消息变化回调
        如果 message 为空，说明提示结束了，恢复默认样式（透明/Tiffany蓝）
        """
        if not message:
            # 恢复为透明背景，文字颜色改回深青色
            self.ui.statusbar.setStyleSheet("QStatusBar { background: #b2dfdb; color: #004D40; border: none; }")

    def load_task_configs(self, instance_id):
        layout = self.ui.scrollAreaWidgetContents.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.config_widgets = []
        if hasattr(self, 'task_summary'):
            self.task_summary.clear_all()
        
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
                if isinstance(widget, CollapsibleBox) and isinstance(box, CollapsibleBox):
                    widget.size_changed.connect(box.refresh_height)

                # 连接启用状态信号到概览面板
                # 使用闭包捕获当前的 cat_name 和 task_name
                # 注意：widget.task_name 是类名，我们需要显示名称
                # 这里我们用 widget.title_label.text() 获取显示的标题
                
                # 定义回调函数
                def on_task_toggled(checked, cat_key=f"cat_{cat_name.lower()}", t_name=widget.title_label.text()):
                    self.task_summary.update_task_status(cat_key, t_name, checked)

                widget.toggled_enable.connect(on_task_toggled)
                
                # 初始化状态
                if widget.isChecked():
                    on_task_toggled(True)

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
            self.ui.text_log.append(f"<font color='green'><b>{get_text('msg_scheduler_started')}</b></font>")
        else:
            sched.stop_scheduler()
            self.ui.text_log.append(f"<font color='red'><b>{get_text('msg_scheduler_stopping')}</b></font>")
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
             # 尝试翻译当前任务名
             trans_key = f"task_{current_task_name.lower()}"
             display_name = get_text(trans_key)
             if display_name == trans_key: display_name = current_task_name
             
             self.ui.list_running.addItem(f"{get_text('lbl_running_title')} {display_name}")
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
            # 翻译任务名
            trans_key = f"task_{task.name.lower()}"
            display_name = get_text(trans_key)
            if display_name == trans_key: display_name = task.name
            
            item = QListWidgetItem(f"[{task.priority}] {display_name}")
            item.setData(Qt.UserRole, task.name) # 依然存储原始类名
            self.ui.list_queue.addItem(item)

        waiting_tasks.sort(key=lambda x: x[0].next_run)
        for task, t_str in waiting_tasks:
            # 翻译任务名
            trans_key = f"task_{task.name.lower()}"
            display_name = get_text(trans_key)
            if display_name == trans_key: display_name = task.name
            
            item = QListWidgetItem(f"{display_name}  ({t_str})")
            item.setData(Qt.UserRole, task.name) # 依然存储原始类名
            self.ui.list_waiting.addItem(item)

    def setup_list_context_menus(self):
        for lst in [self.ui.list_queue, self.ui.list_waiting]:
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(self.on_task_context_menu)

    def on_task_context_menu(self, pos):
        sender_list = self.sender()
        item = sender_list.itemAt(pos)
        if not item: return
        
        task_name = item.data(Qt.UserRole) # 原始类名
        
        # 获取显示名称用于菜单
        trans_key = f"task_{task_name.lower()}"
        display_name = get_text(trans_key)
        if display_name == trans_key: display_name = task_name
        
        menu = QMenu()
        action_run = QAction(f"{get_text('menu_run_now')} {display_name}", self.main_window)
        action_run.triggered.connect(lambda: self.reset_task_next_run(task_name))
        menu.addAction(action_run)
        menu.exec(QCursor.pos())

    def reset_task_next_run(self, task_name):
        if not self.current_instance_id: return
        store = self.manager.get_store(self.current_instance_id)
        store.set_stat(f"tasks.{task_name}.next_run", "")
        self.ui.text_log.append(f"<font color='#1e90ff'>{get_text('msg_force_insert', task_name)}</font>")
    
    def setup_sidebar_context_menu(self):
        self.ui.list_instances.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.list_instances.customContextMenuRequested.connect(self.on_sidebar_menu)

    def on_sidebar_menu(self, pos):
        item = self.ui.list_instances.itemAt(pos)
        if not item: return
        instance_id = item.data(Qt.UserRole)
        
        menu = QMenu()
        action_edit = QAction(get_text("menu_edit_info"), self.main_window)
        action_edit.triggered.connect(lambda: self.do_edit_instance(instance_id))
        menu.addAction(action_edit)

        action_folder = QAction(get_text("menu_open_folder"), self.main_window)
        action_folder.triggered.connect(lambda: self.do_open_folder(instance_id))
        menu.addAction(action_folder)
        
        menu.addSeparator()
        
        action_del = QAction(get_text("menu_delete"), self.main_window)
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
            self.main_window,
            current_name=old_name,
            current_serial=old_serial,
            current_diana=old_diana,
            current_march_slots=old_march
        )
        
        if dialog.exec():
            new_name, new_serial, new_diana, new_march = dialog.get_data()
            if not new_name or not new_serial:
                QMessageBox.warning(self.main_window, get_text("msg_error"), get_text("msg_input_invalid"))
                return

            self.manager.update_instance(
                instance_id,
                new_serial=new_serial,
                new_alias=new_name,
                new_diana_level=new_diana,
                new_march_slots=new_march
            )
            self.ui.text_log.append(f"<font color='blue'>{get_text('msg_instance_updated', new_name, new_diana, new_march)}</font>")

    def do_delete_instance(self, instance_id):
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        name = target['name'] if target else instance_id

        reply = QMessageBox.question(
            self.main_window, 
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
            
            QMessageBox.information(self.main_window, get_text("msg_success"), get_text("msg_success"))

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
        dialog = AddInstanceDialog(self.main_window)
        if dialog.exec():
            name, serial, diana, march = dialog.get_data()
            if not name or not serial:
                QMessageBox.warning(self.main_window, get_text("msg_error"), get_text("msg_input_invalid"))
                return
            
            success, msg = self.manager.create_instance(name, serial, diana, march)
            if success:
                QMessageBox.information(self.main_window, get_text("msg_success"), f"Instance '{name}' created!")
            else:
                QMessageBox.critical(self.main_window, get_text("msg_error"), f"Failed: {msg}")

    def on_refresh_adb(self):
        self.refresh_instances()
        self.ui.statusbar.showMessage("实例列表已刷新", 2000)

    def on_global_settings(self):
        dialog = SettingsDialog(self.main_window)
        if dialog.exec():
            # 如果设置里改了语言，这里需要刷新界面
            self.apply_translations()