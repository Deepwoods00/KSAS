# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QListWidgetItem, QMessageBox, QWidget, 
    QSystemTrayIcon, QMenu, QStyle
)
from PySide6.QtCore import QTimer, Slot, Signal, QFile, QIODevice, QObject, Qt, QEvent
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QColor, QIcon, QAction, QCursor

from instance_manager import InstanceManager
from task_registry import get_all_tasks
from ui.task_widgets import TaskWidgetFactory
from ui.settings_dialog import SettingsDialog
from ui.add_instance_dialog import AddInstanceDialog
from ui.edit_instance_dialog import EditInstanceDialog
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
        
        # 5. 初始化右键菜单 (新增)
        self.setup_list_context_menus()
        self.setup_sidebar_context_menu()
        
        # 6. 初始化界面
        self.refresh_instances()
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_welcome)
        
        # 7. 启动定时器刷新状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_ui_status)
        self.status_timer.start(1000) # 每秒刷新一次

        # 8. 安装事件过滤器
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
        
        # 如果切换了实例，断开旧的信号连接（简单处理：这里暂不处理断连，直接连新的）
        # 实际项目中可能需要更严谨的信号管理
        
        self.current_instance_id = instance_id
        self.ui.stacked_pages.setCurrentWidget(self.ui.page_instance_detail)
        
        # 更新标题
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        if target:
            self.ui.label_instance_name.setText(target.get('alias', instance_id))
            
        # 加载任务配置卡片
        self.load_task_configs(instance_id)
        
        # 连接日志信号
        store = self.manager.get_store(instance_id)
        # 先断开防止重复连接
        try: store.sig_log_msg.disconnect()
        except: pass
        store.sig_log_msg.connect(self.append_log)
        
        # 清空并加载现有日志 (这里可以做成读取 runtime.log 文件)
        self.ui.text_log.clear()
        log_path = os.path.join("data", instance_id, "log", "ksas.log") # 注意 logging_setup 里配的文件名
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    # 只读最后 100 行，防止太卡
                    lines = f.readlines()[-100:]
                    for line in lines:
                        self.ui.text_log.append(f"<span style='color:gray'>{line.strip()}</span>")
            except Exception as e:
                print(f"读取日志失败: {e}")
        self.update_ui_status()

    def append_log(self, level, msg):
        try:
            # 拆分 ID 和 内容
            if "|||" in full_msg:
                sender_id, real_msg = full_msg.split("|||", 1)
            else:
                sender_id = "System"
                real_msg = full_msg
                
            # 🛑 关键判断：只有当消息来源 == 当前选中的实例，才显示！
            if sender_id != self.current_instance_id:
                return
                
            color = "black"
            # ... (颜色逻辑不变) ...
            
            time_str = datetime.now().strftime("%H:%M:%S")
            html = f'<span style="color:gray">[{time_str}]</span> <span style="color:{color}">{real_msg}</span>'
            self.ui.text_log.append(html)
            
        except Exception:
            pass

    def load_task_configs(self, instance_id):
        layout = self.ui.scrollAreaWidgetContents.layout()
        # 清空旧布局
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.config_widgets = []
        
        store = self.manager.get_store(instance_id)
        task_classes = get_all_tasks()
        
        # 动态生成任务卡片
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
            self.ui.text_log.append(f"<font color='green'><b>>>> 调度器已启动 (Scheduler Started)</b></font>")
        else:
            sched.stop_scheduler()
            self.ui.text_log.append(f"<font color='red'><b>>>> 调度器正在停止...</b></font>")
        self.update_ui_status()

    def update_ui_status(self):
        """每秒刷新的核心循环"""
        if not self.current_instance_id:
            return
        
        # 1. 更新按钮状态
        sched = self.manager.get_scheduler(self.current_instance_id)
        if not sched: return
        
        is_running = sched.isRunning()
        
        # 防止按钮状态不同步
        if self.ui.btn_toggle_running.isChecked() != is_running:
            self.ui.btn_toggle_running.setChecked(is_running)
            
        if is_running:
            self.ui.btn_toggle_running.setText("⏹ 停止挂机")
            self.ui.btn_toggle_running.setProperty("state", "running")
            self.ui.label_status_text.setText("Running")
            self.ui.label_status_icon.setText("🟢")
        else:
            self.ui.btn_toggle_running.setText("▶ 启动挂机")
            self.ui.btn_toggle_running.setProperty("state", "stopped")
            self.ui.label_status_text.setText("Idle")
            self.ui.label_status_icon.setText("⚪")
        
        # 强制刷新 QSS 样式
        self.ui.btn_toggle_running.style().unpolish(self.ui.btn_toggle_running)
        self.ui.btn_toggle_running.style().polish(self.ui.btn_toggle_running)

        # 2. 更新资源栏
        store = self.manager.get_store(self.current_instance_id)
        stamina = store.get_stat("stamina", 0)
        self.ui.progress_stamina.setMaximum(200)
        self.ui.progress_stamina.setValue(int(stamina))
        self.ui.progress_stamina.setTextVisible(False) 
        self.ui.label_stamina_val.setText(f"{stamina} / 200")
        
        resources = store.get_stat("resources", {})
        self.ui.val_food.setText(self._format_number(resources.get("food", 0)))
        self.ui.val_wood.setText(self._format_number(resources.get("wood", 0)))
        self.ui.val_stone.setText(self._format_number(resources.get("stone", 0)))
        self.ui.val_iron.setText(self._format_number(resources.get("iron", 0)))

        # 3. 更新任务列表 (Running / Queue / Waiting)
        self.update_task_lists(sched)

    def update_task_lists(self, sched):
        """根据调度器状态刷新中间的三个列表"""
        self.ui.list_running.clear()
        self.ui.list_queue.clear()
        self.ui.list_waiting.clear()
        
        if not sched: return

        store = self.manager.get_store(self.current_instance_id)
        
        # 获取当前正在运行的任务名
        current_task_name = store.get_runtime("current_task", "Idle")
        is_running_logic = store.get_runtime("is_running", False)

        # --- 填充 "运行中" ---
        if is_running_logic and "休眠" not in current_task_name and "待机" not in current_task_name and "Idle" not in current_task_name:
             self.ui.list_running.addItem(f"🔥 {current_task_name}")
        elif is_running_logic:
             self.ui.list_running.addItem(f"💤 {current_task_name}")
        
        # --- 准备数据 ---
        now = datetime.now()
        queue_tasks = []   # 时间到了
        waiting_tasks = [] # 时间没到

        for task in sched.tasks:
            if not task.enabled:
                continue
            
            # 格式化时间
            time_str = task.next_run.strftime("%H:%M:%S") if task.next_run.year > 2000 else "立即"
            
            # 已经在运行的就不显示在队列里了
            if task.name == current_task_name and "休眠" not in current_task_name:
                continue

            if now >= task.next_run:
                queue_tasks.append((task, time_str))
            else:
                waiting_tasks.append((task, time_str))

        # --- 填充 "队列中" (按优先级排序) ---
        # priority 越小越优先
        queue_tasks.sort(key=lambda x: x[0].priority)
        for task, t_str in queue_tasks:
            item = QListWidgetItem(f"[{task.priority}] {task.name}")
            item.setData(Qt.UserRole, task.name) # 存任务名方便右键操作
            self.ui.list_queue.addItem(item)

        # --- 填充 "等待中" (按时间排序) ---
        waiting_tasks.sort(key=lambda x: x[0].next_run)
        for task, t_str in waiting_tasks:
            item = QListWidgetItem(f"{task.name}  ({t_str})")
            item.setData(Qt.UserRole, task.name)
            self.ui.list_waiting.addItem(item)

    # ===========================================
    # 🖱️ 右键菜单逻辑 (Context Menu)
    # ===========================================
    def setup_list_context_menus(self):
        """设置列表的右键菜单策略"""
        for lst in [self.ui.list_queue, self.ui.list_waiting]:
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(self.on_task_context_menu)

    def on_task_context_menu(self, pos):
        """处理右键点击"""
        sender_list = self.sender() # 获取是哪个列表发出的信号
        item = sender_list.itemAt(pos)
        
        if not item: return
        
        task_name = item.data(Qt.UserRole)
        
        menu = QMenu()
        action_run = QAction(f"🚀 立即执行 {task_name}", self.ui)
        action_run.triggered.connect(lambda: self.reset_task_next_run(task_name))
        menu.addAction(action_run)
        
        menu.exec(QCursor.pos())

    def reset_task_next_run(self, task_name):
        """重置任务时间 -> 立即执行"""
        if not self.current_instance_id: return
        
        store = self.manager.get_store(self.current_instance_id)
        # 清空 next_run，调度器会认为是公元1年，从而立即执行
        store.set_stat(f"tasks.{task_name}.next_run", "")
        
        self.ui.text_log.append(f"<font color='#1e90ff'>[User] 已强制插队任务: {task_name}</font>")
    
    def setup_sidebar_context_menu(self):
        """设置左侧实例列表的右键菜单"""
        self.ui.list_instances.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.list_instances.customContextMenuRequested.connect(self.on_sidebar_menu)

    def on_sidebar_menu(self, pos):
        item = self.ui.list_instances.itemAt(pos)
        if not item: return
        
        instance_id = item.data(Qt.UserRole)
        
        # 创建菜单
        menu = QMenu()
        
        # ✏️ 修改地址
        action_edit = QAction("✏️ 编辑实例信息 (Edit Info)", self.ui)
        action_edit.triggered.connect(lambda: self.do_edit_instance(instance_id)) 
        menu.addAction(action_edit)

        # 📂 打开文件夹
        action_folder = QAction("📂 打开数据目录 (Open Folder)", self.ui)
        action_folder.triggered.connect(lambda: self.do_open_folder(instance_id))
        menu.addAction(action_folder)
        
        menu.addSeparator()
        
        # 🗑️ 删除实例
        action_del = QAction("🗑️ 删除实例 (Delete)", self.ui)
        # 红色字体警示
        # action_del.setStyleSheet("color: red;") # Qt Menu styleSheet 有点难搞，先不管颜色
        action_del.triggered.connect(lambda: self.do_delete_instance(instance_id))
        menu.addAction(action_del)
        
        menu.exec(QCursor.pos())

    def do_edit_instance(self, instance_id):
        """弹出对话框修改 Name 和 Serial"""
        
        # 1. 获取旧数据，用来填在框里
        store = self.manager.get_store(instance_id)
        # 从注册表里拿现在的名字（别名）
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        
        old_name = target['name'] if target else instance_id
        old_serial = store.get_cfg("meta.serial", "")
        
        # 2. 弹出对话框
        dialog = EditInstanceDialog(self.ui, current_name=old_name, current_serial=old_serial)
        
        if dialog.exec():
            new_name, new_serial = dialog.get_data()
            
            # 简单校验
            if not new_name or not new_serial:
                QMessageBox.warning(self.ui, "无效输入", "名称和地址不能为空！")
                return

            # 3. 调用 Manager 更新
            # (注意：instance_manager.py 里的 update_instance 方法要确保已存在)
            self.manager.update_instance(instance_id, new_serial=new_serial, new_alias=new_name)
            
            self.ui.text_log.append(f"<font color='blue'>[System] 实例信息已更新: {new_name} ({new_serial})</font>")

    def do_delete_instance(self, instance_id):
        """删除实例确认"""
        # 获取名字用于提示
        all_insts = self.manager.get_all_instances()
        target = next((x for x in all_insts if x['id'] == instance_id), None)
        name = target['name'] if target else instance_id

        reply = QMessageBox.question(
            self.ui, 
            "确认删除", 
            f"确定要删除实例 [{name}] 吗？\n\n"
            "• 配置文件将被移除\n"
            "• 统计数据将被清空\n"
            "• 此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 如果正在运行，先停止
            sched = self.manager.get_scheduler(instance_id)
            if sched and sched.isRunning():
                sched.stop_scheduler()
                
            self.manager.delete_instance(instance_id)
            
            # 如果删的是当前选中的，清空右侧
            if self.current_instance_id == instance_id:
                self.current_instance_id = None
                self.ui.stacked_pages.setCurrentIndex(0) # 回到欢迎页
            
            QMessageBox.information(self.ui, "提示", "删除成功")

    def do_open_folder(self, instance_id):
        """打开该实例的文件夹"""
        store = self.manager.get_store(instance_id)
        if store:
            path = os.path.abspath(store.base_dir)
            os.startfile(path)

    # ===========================================
    # 🔢 数字格式化
    # ===========================================
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