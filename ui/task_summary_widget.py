# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView
from PySide6.QtCore import Qt, QEvent
from i18n.i18n import get_text

class TaskSummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.categories = {} # Map category_key -> QTreeWidgetItem
        self.tasks = {}      # Map task_name -> QTreeWidgetItem

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.lbl_title = QLabel(get_text("lbl_enabled_tasks"))
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 12pt; color: #00695C; margin-bottom: 5px;")
        layout.addWidget(self.lbl_title)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        self.tree.setAnimated(True) # Enable animation
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded) # Ensure scrollbar
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Disable default click behavior to handle it manually on release
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.itemPressed.connect(lambda item, col: None) # Consume press
        self.tree.itemClicked.connect(lambda item, col: None) # Consume click
        # Use itemPressed to detect start of click, but we want release.
        # QTreeWidget doesn't have itemReleased signal.
        # We can override mouseReleaseEvent or use clicked signal which is usually on release for buttons but maybe not items.
        # Actually, QAbstractItemView::clicked is emitted on mouse release.
        # But default expansion happens on pressed or double clicked.
        
        # Let's try to customize the behavior by subclassing or event filter if needed.
        # But for now, let's just set style.
        # To change expansion to release, we might need to subclass QTreeWidget.
        
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #E0F2F1;
                border: 1px solid #00897B;
                border-radius: 5px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
        """)
        layout.addWidget(self.tree)
        
        # Install event filter to handle mouse release for expansion
        self.tree.viewport().installEventFilter(self)

    def eventFilter(self, source, event):
        if source == self.tree.viewport():
            if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                item = self.tree.itemAt(event.pos())
                if item:
                    # Toggle expansion state
                    item.setExpanded(not item.isExpanded())
                    return True
            elif event.type() == QEvent.MouseButtonPress:
                # Consume press event to prevent default expansion on press
                return True
            elif event.type() == QEvent.MouseButtonDblClick:
                # Consume double click to prevent default behavior
                return True
        return super().eventFilter(source, event)

    def update_task_status(self, category_key, task_name, is_enabled):
        """
        Update the display status of a task.
        :param category_key: Translation key for category (e.g., 'cat_combat')
        :param task_name: Display name of the task (already translated or raw)
        :param is_enabled: Boolean
        """
        # 1. Handle Category Item
        cat_item = self.categories.get(category_key)
        if not cat_item:
            cat_text = get_text(category_key)
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, cat_text)
            cat_item.setExpanded(True)
            # Make category bold
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            
            self.categories[category_key] = cat_item

        # 2. Handle Task Item
        # We use a unique key for the task item in our map: "category_key|task_name"
        # to avoid collisions if same task name exists in different categories (unlikely but safe)
        unique_key = f"{category_key}|{task_name}"
        task_item = self.tasks.get(unique_key)

        if is_enabled:
            if not task_item:
                task_item = QTreeWidgetItem(cat_item)
                task_item.setText(0, task_name)
                self.tasks[unique_key] = task_item
        else:
            if task_item:
                cat_item.removeChild(task_item)
                del self.tasks[unique_key]

        # 3. Cleanup empty categories
        if cat_item.childCount() == 0:
            # If category is empty, hide or remove it? 
            # Let's remove it to keep it clean
            index = self.tree.indexOfTopLevelItem(cat_item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)
            del self.categories[category_key]

    def clear_all(self):
        self.tree.clear()
        self.categories.clear()
        self.tasks.clear()

    def retranslate_ui(self):
        self.lbl_title.setText(get_text("lbl_enabled_tasks"))
        # We might need to refresh categories text if language changes, 
        # but usually a full refresh is triggered by MainWindowLogic.