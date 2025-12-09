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
    QGroupBox, QLabel, QVBoxLayout, QHBoxLayout, QSplitter, 
    QApplication, QTreeWidget, QTreeWidgetItem, QStackedWidget, QScrollArea, QFrame,
    QAbstractItemView
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
from ui.task_summary_widget import TaskSummaryWidget

# ============================================================================
# 💓 KeyAuth 心跳线程
# ============================================================================
class KeyAuthHeartbeatThread(QThread):
    sig_auth_failed = Signal(str)

    def __init__(self, keyauth_app):
        super().__init__()
        self.setObjectName("KeyAuth_Thread")
        self.api = keyauth_app
        self._exit_event = threading.Event()
        self.failed_attempts = 0
        self.INTERVAL_NORMAL = 30 * 60  # 30分钟
        self.INTERVAL_RETRY = 3 * 60    # 3分钟
        self.MAX_RETRIES = 3

    def stop(self):
        print("[Heartbeat] Stop signal received.")
        self._exit_event.set()
        if not self.wait(2000): 
            print("[Heartbeat] Thread stuck. Forcing terminate.")
            self.terminate()
            self.wait()

    def run(self):
        if self._exit_event.wait(self.INTERVAL_NORMAL):
            return 

        while not self._exit_event.is_set():
            try:
                is_valid = self.api.check()
                if self._exit_event.is_set(): break

                if is_valid:
                    self.failed_attempts = 0
                    if self._exit_event.wait(self.INTERVAL_NORMAL): return 
                else:
                    self.failed_attempts += 1
                    print(f"[Heartbeat] Check failed ({self.failed_attempts}/{self.MAX_RETRIES})")
                    if self.failed_attempts >= self.MAX_RETRIES:
                        self.sig_auth_failed.emit(f"Heartbeat failed {self.MAX_RETRIES} times.")
                        break 
                    else:
                        if self._exit_event.wait(self.INTERVAL_RETRY): return

            except Exception as e:
                self.failed_attempts += 1
                print(f"[Heartbeat] Exception: {e}")
                if self.failed_attempts >= self.MAX_RETRIES:
                    self.sig_auth_failed.emit(f"Network exception: {str(e)}")
                    break
                else:
                    if self._exit_event.wait(self.INTERVAL_RETRY): return
        print("[Heartbeat] Thread loop finished.")


# ============================================================================
# 🖥️ 主窗口逻辑
# ============================================================================
class MainWindowLogic(QObject):
    def __init__(self, keyauth_app=None):
        print(">>> 正在初始化 MainWindowLogic，参数:", keyauth_app)
        super().__init__()
        
        self.main_window = QMainWindow()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.main_window)
        
        # [修改点 1] 设置默认窗口大小为 1280x800
        self.main_window.resize(1100, 730)
        
        self.manager = InstanceManager()
        self.current_instance_id = None
        self.config_widgets = [] 
        self.task_widget_map = {} 
        
        self.manager.sig_instance_list_changed.connect(self.refresh_instances)
        self.init_system_tray()
        self.rearrange_sidebar_buttons()

        self.ui.list_instances.itemClicked.connect(self.on_instance_selected)
        self.ui.btn_add_instance.clicked.connect(self.on_add_instance)
        self.ui.btn_refresh_adb.clicked.connect(self.on_refresh_adb)
        self.ui.btn_toggle_running.clicked.connect(self.on_toggle_running)
        self.ui.btn_global_settings.clicked.connect(self.on_global_settings)
        self.ui.btn_minimize.clicked.connect(self.minimize_to_tray)
        
        self.setup_list_context_menus()
        self.setup_sidebar_context_menu()
        
        self.refresh_instances()
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_welcome)
        
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_ui_status)
        self.status_timer.start(1000) 

        self.main_window.installEventFilter(self) 
        self.ui.progress_stamina.installEventFilter(self)
        self.ui.label_stamina_val.installEventFilter(self)

        self.setup_stats_page()
        
        self.apply_translations()

        self.keyauth_thread = None
        if keyauth_app:
            self.start_heartbeat(keyauth_app)

        self.ui.statusbar.setSizeGripEnabled(False)
        self.ui.statusbar.setStyleSheet("QStatusBar { background: #b2dfdb; color: #004D40; border: none; }")
        self.ui.statusbar.messageChanged.connect(self.on_statusbar_changed)

    def start_heartbeat(self, keyauth_app):
        self.keyauth_thread = KeyAuthHeartbeatThread(keyauth_app)
        self.keyauth_thread.sig_auth_failed.connect(self.on_auth_failed_emergency)
        self.keyauth_thread.start()
        print("[System] Security heartbeat started (Interval: 30m, Redundancy: 3x3m).")

    def on_auth_failed_emergency(self, reason):
        print(f"[Security] EMERGENCY STOP: {reason}")
        running_count = 0
        all_schedulers = self.manager.schedulers
        
        for instance_id, sched in all_schedulers.items():
            if sched.isRunning():
                sched.stop_scheduler()
                running_count += 1
                store = self.manager.get_store(instance_id)
                if store:
                    store.push_log(get_text("msg_heartbeat_fail", reason), "ERROR")

        self.update_ui_status()
        self.ui.btn_toggle_running.setEnabled(False)
        self.ui.btn_toggle_running.setText(get_text("btn_auth_invalid"))
        self.ui.btn_toggle_running.setStyleSheet("background-color: gray; color: white;")
        
        QMessageBox.critical(
            self.main_window,
            get_text("title_auth_failed"),
            get_text("msg_heartbeat_fail", reason)
        )

    # ------------------------------------------------------------------------
    # 🧩 界面布局与初始化 (重构部分)
    # ------------------------------------------------------------------------

    def setup_stats_page(self):
        """在 Stats 页面动态添加控件"""
        parent_widget = self.ui.group_stamina.parent()
        layout = parent_widget.layout()
        
        if not layout:
            layout = QVBoxLayout(parent_widget)
            
        self.group_sidebar = QWidget(parent_widget)
        self.group_sidebar.setObjectName("group_sidebar")
        vbox = QVBoxLayout(self.group_sidebar)
        vbox.setContentsMargins(0, 10, 0, 10) 
        
        self.label_idle_queues_title = QLabel(self.group_sidebar)
        self.label_idle_queues_val = QLabel("?", self.group_sidebar)
        self.label_idle_queues_val.setStyleSheet("font-weight: bold; color: green; font-size: 12pt;")
        
        hbox = QGridLayout()
        hbox.addWidget(self.label_idle_queues_title, 0, 0)
        hbox.addWidget(self.label_idle_queues_val, 0, 1)
        hbox.setColumnStretch(1, 1)
        
        vbox.addLayout(hbox)
        layout.addWidget(self.group_sidebar)

        self.hero_widget = HeroManagementWidget(parent_widget)
        layout.addWidget(self.hero_widget)
        layout.addStretch()

    def apply_translations(self):
        self.ui.btn_add_instance.setText(get_text("btn_add_instance"))
        self.ui.btn_add_instance.setToolTip(get_text("btn_add_instance"))
        self.ui.btn_refresh_adb.setText(get_text("btn_refresh_adb"))
        self.ui.btn_global_settings.setText(get_text("btn_global_settings"))
        self.ui.btn_minimize.setText(get_text("btn_minimize"))
        self.ui.btn_minimize.setToolTip(get_text("btn_minimize")) 
        
        self.ui.label_welcome.setText(get_text("lbl_welcome"))
        self.update_ui_status() 
        
        self.ui.tabWidget.setTabText(0, get_text("tab_tasks"))
        self.ui.tabWidget.setTabText(1, get_text("tab_logs"))
        self.ui.tabWidget.setTabText(2, get_text("tab_stats"))
        
        if hasattr(self.ui, 'group_stamina'):
            self.ui.group_stamina.setTitle(get_text("group_stamina"))
            
        if hasattr(self, 'group_sidebar'):
            self.label_idle_queues_title.setText(get_text("lbl_idle_queues"))

        if hasattr(self.ui, 'lbl_running_title'):
            self.ui.lbl_running_title.setText(get_text("lbl_running_title"))
        if hasattr(self.ui, 'lbl_queue_title'):
            self.ui.lbl_queue_title.setText(get_text("lbl_queue_title"))
        if hasattr(self.ui, 'lbl_waiting_title'):
            self.ui.lbl_waiting_title.setText(get_text("lbl_waiting_title"))

        if hasattr(self, 'task_summary'):
            self.task_summary.retranslate_ui()

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
        container = self.ui.sidebar_tools
        old_layout = container.layout()
        
        btn_add = self.ui.btn_add_instance
        btn_refresh = self.ui.btn_refresh_adb
        btn_settings = self.ui.btn_global_settings
        btn_minimize = self.ui.btn_minimize
        
        new_layout = QGridLayout()
        new_layout.setSpacing(5)
        new_layout.setContentsMargins(5, 5, 5, 5)
        
        new_layout.addWidget(btn_add, 0, 0)
        new_layout.addWidget(btn_refresh, 0, 1)
        new_layout.addWidget(btn_settings, 1, 0)
        new_layout.addWidget(btn_minimize, 1, 1)
        
        QWidget().setLayout(old_layout)
        container.setLayout(new_layout)

    def eventFilter(self, obj, event):
        if obj == self.main_window and event.type() == QEvent.Close:
            if global_config.get("close_to_tray", False):
                event.ignore()
                self.main_window.hide()
                self.tray_icon.showMessage(get_text("msg_app_hidden"), get_text("msg_click_restore"), QSystemTrayIcon.Information, 2000)
                return True
            else:
                self.quit_app()
                return False
        
        if event.type() == QEvent.MouseButtonDblClick:
            if obj == self.ui.progress_stamina or obj == self.ui.label_stamina_val:
                self.do_edit_stamina()
                return True

        return super().eventFilter(obj, event)

    def do_edit_stamina(self):
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

    def show_window(self):
        self.main_window.showNormal()
        self.main_window.activateWindow()

    def quit_app(self):
        self.tray_icon.hide()
        if hasattr(self, 'keyauth_thread') and self.keyauth_thread:
            if self.keyauth_thread.isRunning():
                print("[System] Stopping KeyAuth thread...")
                self.keyauth_thread.stop()
                self.keyauth_thread.wait() 
        if hasattr(self, 'manager'):
            for instance_id, sched in self.manager.schedulers.items():
                if sched.isRunning():
                    print(f"[System] Stopping scheduler for {instance_id}...")
                    sched.stop_scheduler()
                    sched.wait(2000)
        print("[System] All threads stopped. Quitting Qt loop.")
        QApplication.instance().quit()

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

        try: store.sig_config_changed.disconnect(self.show_config_saved_msg)
        except: pass
        store.sig_config_changed.connect(self.show_config_saved_msg)

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
                        line = line.strip()
                        if not line: continue
                        color = self._get_log_color(line)
                        html = f"<span style='color:{color}'>{line}</span>"
                        self.ui.text_log.append(html)
            except Exception as e:
                print(f"读取日志失败: {e}")
        self.update_ui_status()

    def _get_log_color(self, text):
        text_upper = text.upper()
        text_lower = text.lower()
        if "ERROR" in text_upper: return "red"
        elif "WARNING" in text_upper: return "#FF8C00"
        if any(k in text_lower for k in ["start", "启动", "开始"]): return "#008000"
        elif any(k in text_lower for k in ["stop", "停止", "结束"]): return "#B22222"
        elif any(k in text_lower for k in ["sleep", "wait", "休眠", "等待"]): return "#4682B4"
        elif any(k in text_lower for k in ["recover", "stamina", "体力"]): return "#20B2AA"
        elif "success" in text_lower or "成功" in text_lower: return "#008000"
        return "black"

    def append_log(self, level, full_msg):
        try:
            if "|||" in full_msg:
                sender_id, real_msg = full_msg.split("|||", 1)
            else:
                sender_id = "System"
                real_msg = full_msg
                
            if sender_id != self.current_instance_id: return
            
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
        short_key = key.replace("modules.", "")
        msg = get_text("msg_config_saved", short_key, value)
        self.ui.statusbar.setStyleSheet("QStatusBar { background-color: #00695C; color: white; font-weight: bold; font-size: 11pt; }")
        self.ui.statusbar.showMessage(msg, 3000)
        time_str = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:black">[{time_str}]</span> <span style="color:#800080">{msg}</span>'
        self.ui.text_log.append(html)
        self.ui.text_log.ensureCursorVisible()

    def on_statusbar_changed(self, message):
        if not message:
            self.ui.statusbar.setStyleSheet("QStatusBar { background: #b2dfdb; color: #004D40; border: none; }")

    # ------------------------------------------------------------------------
    # 🌟 核心修改：构建三栏布局 (Tree + Stack + TaskSummary)
    # ------------------------------------------------------------------------
    def load_task_configs(self, instance_id):
        """
        加载任务配置，构建 三栏布局: Tree | Config Stack | Task Summary
        """
        # 0. 重置映射
        self.task_widget_map = {}

        # 1. 清理旧布局
        if self.ui.tab_tasks.layout():
            old_layout = self.ui.tab_tasks.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    pass
            QWidget().setLayout(old_layout) 

        # 2. 创建新布局 (水平)
        main_layout = QHBoxLayout(self.ui.tab_tasks)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 3. 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4) # 增加把手宽度，方便拖拽
        splitter.setStyleSheet("QSplitter::handle { background-color: #B0BEC5; }")
        main_layout.addWidget(splitter)

        # === 左侧：导航树 (Tiffany 风格) ===
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setIndentation(15)
        self.nav_tree.setRootIsDecorated(False) # 隐藏小三角
        self.nav_tree.setItemsExpandable(False) # 禁用默认展开
        self.nav_tree.setAnimated(True)         # 启用动画 (Requirement 2)
        
        # 配合 CheckBox 的样式
        self.nav_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #E0F2F1; /* 极浅青色背景 (Light Tiffany) */
                color: #004D40;            /* 深青色文字 */
                border: none;
                font-size: 10pt;
                outline: 0;
            }
            QTreeWidget::item {
                padding: 8px 5px;          /* 调整内边距 */
                margin: 0px;
                border-left: 3px solid transparent; 
            }
            QTreeWidget::item:hover {
                background-color: #B2DFDB; 
            }
            QTreeWidget::item:selected {
                background-color: #ffffff; 
                color: #00695C;
                border-left: 3px solid #009688; 
                font-weight: bold;
            }
            /* 调整 CheckBox 样式 */
            QTreeWidget::indicator {
                width: 16px;
                height: 16px;
            }
            QTreeWidget::indicator:unchecked {
                border: 1px solid #00897B;
                background-color: #ffffff;
                border-radius: 2px;
            }
            QTreeWidget::indicator:checked {
                border: 1px solid #00897B;
                background-color: #00897B;
                border-radius: 2px;
            }
        """)
        # 移除固定宽度，改用最小宽度 (Requirement 3)
        self.nav_tree.setMinimumWidth(130) # 约 200 * 2/3
        splitter.addWidget(self.nav_tree)

        # === 中间：配置详情区域 (ScrollArea + StackedWidget) ===
        middle_container = QWidget()
        middle_container.setStyleSheet("background-color: #FFFFFF;") # 白色背景
        middle_layout = QVBoxLayout(middle_container)
        middle_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        
        self.config_stack = QStackedWidget()
        self.scroll_area.setWidget(self.config_stack)
        
        middle_layout.addWidget(self.scroll_area)
        splitter.addWidget(middle_container)

        # === 右侧：任务清单 (Task Summary) - 恢复显示 ===
        self.task_summary = TaskSummaryWidget()
        # [修改点 2] 将最小宽度设置为 130 (原 220 的约 3/5)
        self.task_summary.setMinimumWidth(130)
        splitter.addWidget(self.task_summary)

        # [修改点 3] 设置分割比例 (Nav : Config : Summary)
        # 给中间留最大空间，左右两边较小
        splitter.setSizes([220, 1500, 130])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # --- 4. 填充内容 ---
        self.config_widgets = []
        if hasattr(self, 'task_summary'):
            self.task_summary.clear_all()

        store = self.manager.get_store(instance_id)
        task_classes = get_all_tasks()
        
        # 4.1 分类逻辑
        categories = {}
        default_category_map = {
            "GeneralSettings": "General",
            "WolfTask": "Combat", "BeastTask": "Combat", "RallyTask": "Combat",
            "IntelTask": "Daily", "GatherTask": "Daily",
            "RecruitAdvTask": "Daily", "RecruitEpicTask": "Daily",
            "AllianceHelpTask": "Daily", "AllianceTechTask": "Daily", "AllianceChestTask": "Daily",
            "MailTask": "Daily", "StaminaControlTask": "Daily", 
            "TroopTrainingTask": "Daily", "WarehouseTask": "Daily",
            "ShopTask": "Shop",
            "TestSidebarTask": "Other", "ExampleTask": "Other"
        }

        for task_cls in task_classes:
            menu = "Other"
            if hasattr(task_cls, 'config_schema'):
                for item in task_cls.config_schema:
                    if 'menu' in item:
                        menu = item['menu']
                        break
            if menu == "Other":
                menu = default_category_map.get(task_cls.__name__, "Other")
            
            if menu not in categories: categories[menu] = []
            categories[menu].append(task_cls)

        # 排序
        sorted_cats = sorted(categories.keys())
        if "General" in sorted_cats:
            sorted_cats.remove("General")
            sorted_cats.insert(0, "General") 
        if "Other" in sorted_cats:
            sorted_cats.remove("Other")
            sorted_cats.append("Other")

        # 4.2 构建树节点
        for cat_name in sorted_cats:
            tasks = categories[cat_name]
            if not tasks: continue
            
            # 分类节点 (顶级)
            trans_key = f"cat_{cat_name.lower()}"
            cat_display = get_text(trans_key)
            if cat_display == trans_key: cat_display = cat_name
            
            cat_item = QTreeWidgetItem(self.nav_tree)
            # 这里的文本不带箭头，因为我们自己控制展开
            cat_item.setText(0, cat_display)
            
            # 设置样式：粗体
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            # 设置数据：标记这是一个父节点
            cat_item.setData(0, Qt.UserRole, "PARENT_NODE") 
            
            # [修改点 4] 默认收起 (Requirement 1)
            cat_item.setExpanded(False)

            for task_cls in tasks:
                # 创建配置 Widget
                widget = TaskWidgetFactory.create_widget(task_cls)
                widget.load_from_store(store)
                
                # 添加到 Stack
                index = self.config_stack.addWidget(widget)
                self.config_widgets.append(widget)
                
                # 添加到 Tree (作为子节点)
                task_display = widget.title_label.text()
                
                child_item = QTreeWidgetItem(cat_item)
                child_item.setText(0, task_display)
                child_item.setData(0, Qt.UserRole, index) # 存储 stack 索引

                # === 关键 1: 子任务前加复选框 ===
                # 跳过 GeneralSettings，因为它不是任务，不需要开关
                if task_cls.__name__ != "GeneralSettings":
                    child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)
                    # 初始化状态 (从 widget 读取)
                    initial_state = Qt.Checked if widget.isChecked() else Qt.Unchecked
                    child_item.setCheckState(0, initial_state)
                    
                    # 缓存映射: 树节点 <-> Widget
                    # key可以用 task_cls.__name__ 或者 unique_id
                    task_id = task_cls.__name__
                    self.task_widget_map[task_id] = {
                        "tree_item": child_item,
                        "widget": widget
                    }

                    # === 关键 2: 双向绑定 (Widget -> Tree) ===
                    # 当详情页的开关变化时，更新左侧树的勾选框
                    # 注意：为了防止无限循环，需要小心处理
                    def sync_tree_from_widget(checked, item=child_item):
                        new_state = Qt.Checked if checked else Qt.Unchecked
                        if item.checkState(0) != new_state:
                            # 屏蔽树的信号，防止触发 widget 更新
                            self.nav_tree.blockSignals(True)
                            item.setCheckState(0, new_state)
                            self.nav_tree.blockSignals(False)
                    
                    widget.toggled_enable.connect(sync_tree_from_widget)
                
                # === 连接右侧任务列表 ===
                def on_task_toggled(checked, cat_key=f"cat_{cat_name.lower()}", t_name=task_display):
                    self.task_summary.update_task_status(cat_key, t_name, checked)

                widget.toggled_enable.connect(on_task_toggled)
                
                # 初始化状态
                if widget.isChecked():
                    on_task_toggled(True)

        # 5. 连接信号
        # 点击切换页面 (鼠标松开时触发，符合需求)
        self.nav_tree.itemClicked.connect(self.on_tree_item_clicked)
        # 复选框变化 (itemChanged 信号包含 checkState 变化)
        self.nav_tree.itemChanged.connect(self.on_tree_item_changed)
        
        # 默认选中第一个可选项 (General or first category)
        it = self.nav_tree.topLevelItem(0)
        if it:
            # 展开第一个分类，以便用户不是看到一片空白
            it.setExpanded(True)
            if it.childCount() > 0:
                self.nav_tree.setCurrentItem(it.child(0))
                self.config_stack.setCurrentIndex(it.child(0).data(0, Qt.UserRole))

    def on_tree_item_clicked(self, item, column):
        """自定义树节点点击逻辑"""
        # 1. 如果是父节点 (分类) -> 切换展开/收起
        if item.data(0, Qt.UserRole) == "PARENT_NODE":
            item.setExpanded(not item.isExpanded())
            return
        
        # 2. 如果是子节点 (任务) -> 切换右侧 Stack 页面
        index = item.data(0, Qt.UserRole)
        if index is not None and isinstance(index, int):
            self.config_stack.setCurrentIndex(index)

    def on_tree_item_changed(self, item, column):
        """处理左侧树复选框变化 (Tree -> Widget)"""
        # 只处理复选框列 (column 0)
        if column != 0: return
        
        # 找到对应的 Widget
        # 我们可以通过遍历 map 找到对应的 item
        # 或者更简单的，item 对应的 widget 就在 stack 的 index 位置
        index = item.data(0, Qt.UserRole)
        if index is not None and isinstance(index, int) and index < self.config_stack.count():
            widget = self.config_stack.widget(index)
            
            # 判断是否是 General (没有复选框)
            if hasattr(widget, 'setChecked'):
                is_checked = (item.checkState(0) == Qt.Checked)
                
                # 如果状态不一致，更新 Widget
                if widget.isChecked() != is_checked:
                    # widget.setChecked 会触发 toggled_enable 信号
                    # 从而触发 sync_tree_from_widget
                    # 所以 sync_tree_from_widget 里加了 blockSignals 很重要
                    widget.setChecked(is_checked)

    def save_current_configs(self):
        if not self.current_instance_id: return
        store = self.manager.get_store(self.current_instance_id)
        for widget in self.config_widgets:
            widget.save_to_store(store)

    def on_toggle_running(self):
        if not self.current_instance_id: return
        self.save_current_configs()
        
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched: return

        if self.ui.btn_toggle_running.isChecked():
            sched.start_scheduler()
            self.ui.text_log.append(f"<font color='green'><b>{get_text('msg_scheduler_started')}</b></font>")
        else:
            sched.stop_scheduler()
            self.ui.text_log.append(f"<font color='red'><b>{get_text('msg_scheduler_stopping')}</b></font>")
        self.update_ui_status()

    def update_ui_status(self):
        if not self.current_instance_id: return
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched: return
        
        is_running = sched.isRunning()
        if self.ui.btn_toggle_running.isChecked() != is_running:
            self.ui.btn_toggle_running.setChecked(is_running)
            
        if is_running:
            self.ui.btn_toggle_running.setText(get_text("btn_stop"))
            self.ui.btn_toggle_running.setProperty("state", "running")
            self.ui.label_status_text.setText(get_text("lbl_status_running"))
            self.ui.label_status_icon.setText("🟢")
        else:
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
            if not task.enabled: continue
            time_str = task.next_run.strftime("%H:%M:%S") if task.next_run.year > 2000 else "立即"
            if task.name == current_task_name and "休眠" not in current_task_name: continue

            if now >= task.next_run:
                queue_tasks.append((task, time_str))
            else:
                waiting_tasks.append((task, time_str))

        queue_tasks.sort(key=lambda x: x[0].priority)
        for task, t_str in queue_tasks:
            trans_key = f"task_{task.name.lower()}"
            display_name = get_text(trans_key)
            if display_name == trans_key: display_name = task.name
            item = QListWidgetItem(f"[{task.priority}] {display_name}")
            item.setData(Qt.UserRole, task.name)
            self.ui.list_queue.addItem(item)

        waiting_tasks.sort(key=lambda x: x[0].next_run)
        for task, t_str in waiting_tasks:
            trans_key = f"task_{task.name.lower()}"
            display_name = get_text(trans_key)
            if display_name == trans_key: display_name = task.name
            item = QListWidgetItem(f"{display_name}  ({t_str})")
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
            self.manager.update_instance(instance_id, new_serial=new_serial, new_alias=new_name, new_diana_level=new_diana, new_march_slots=new_march)
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
            self.apply_translations()