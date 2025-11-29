# -*- coding: utf-8 -*-
from PySide6.QtCore import Slot, Signal, Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QAbstractAnimation, QSize, QEvent
from PySide6.QtWidgets import QWidget, QToolButton, QVBoxLayout, QHBoxLayout, QFrame, QScrollArea, QSizePolicy, QCheckBox, QLabel

class AutoHeightScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

    def eventFilter(self, o, e):
        if o == self.widget() and e.type() == QEvent.Resize:
            self.updateGeometry()
        return super().eventFilter(o, e)

    def setWidget(self, widget):
        super().setWidget(widget)
        if widget:
            widget.installEventFilter(self)

    def sizeHint(self):
        if self.widget():
            # Add a small buffer to prevent cutting off content
            h = self.widget().sizeHint().height() + 5
            if self.maximumHeight() < 16777215:
                h = min(h, self.maximumHeight())
            return QSize(super().sizeHint().width(), h)
        return QSize(0, 0)

class CollapsibleBox(QWidget):
    # Signal when the content visibility toggles (expanded/collapsed)
    toggled_state = Signal(bool)
    # Signal when the checkbox is toggled (enabled/disabled)
    toggled_enable = Signal(bool)
    # Signal when the size of the box changes (e.g. after animation)
    size_changed = Signal()

    def __init__(self, title="", parent=None, checkable=False):
        super().__init__(parent)

        self.is_checkable = checkable
        
        # --- Header ---
        self.header_widget = QWidget()
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(5)

        # 1. Arrow Button
        self.toggle_button = QToolButton()
        self.toggle_button.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.clicked.connect(self.on_toggle)
        self.header_layout.addWidget(self.toggle_button)

        # 2. Checkbox (Optional)
        self.checkbox = None
        if checkable:
            self.checkbox = QCheckBox()
            self.checkbox.toggled.connect(self.on_checkbox_toggled)
            self.header_layout.addWidget(self.checkbox)

        # 3. Title Label
        self.title_label = QLabel(title)
        self.title_label.mousePressEvent = self.on_title_clicked
        self.header_layout.addWidget(self.title_label)
        
        self.header_layout.addStretch()

        # --- Content ---
        self.toggle_animation = QParallelAnimationGroup(self)
        self.toggle_animation.finished.connect(self.on_animation_finished)

        self.content_area = AutoHeightScrollArea()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setVisible(False)

        # --- Main Layout ---
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.header_widget)
        lay.addWidget(self.content_area)

        self.anim_max = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim_min = QPropertyAnimation(self.content_area, b"minimumHeight")
        
        self.anim_max.valueChanged.connect(self.on_animation_value_changed)
        self.anim_min.valueChanged.connect(self.on_animation_value_changed)
        
        self.toggle_animation.addAnimation(self.anim_max)
        self.toggle_animation.addAnimation(self.anim_min)

    def on_animation_value_changed(self, value):
        self.content_area.updateGeometry()
        self.updateGeometry()
        self.size_changed.emit()

    def on_title_clicked(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_button.click()

    @Slot()
    def on_toggle(self):
        if self.toggle_animation.state() == QAbstractAnimation.Running:
            # If animating, ignore or handle gracefully.
            self.toggle_button.setChecked(not self.toggle_button.isChecked())
            return

        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        
        # Always use Forward because we explicitly set Start/End values for both directions
        self.toggle_animation.setDirection(QPropertyAnimation.Forward)

        # Calculate content height
        content_height = 0
        if self.content_area.widget():
            self.content_area.widget().adjustSize()
            content_height = self.content_area.widget().sizeHint().height() + 5

        if checked:
            # Expanding: 0 -> content_height
            self.content_area.setVisible(True)
            self.anim_max.setStartValue(0)
            self.anim_max.setEndValue(content_height)
            self.anim_min.setStartValue(0)
            self.anim_min.setEndValue(content_height)
        else:
            # Collapsing: current -> 0
            # Snap to current height first (in case it was unlocked/MAX)
            current_h = self.content_area.height()
            self.content_area.setMaximumHeight(current_h)
            self.content_area.setMinimumHeight(current_h)
            
            self.anim_max.setStartValue(current_h)
            self.anim_max.setEndValue(0)
            self.anim_min.setStartValue(current_h)
            self.anim_min.setEndValue(0)

        self.toggle_animation.start()
        self.toggled_state.emit(checked)

    @Slot()
    def on_animation_finished(self):
        if self.toggle_button.isChecked():
            # Expanded: Unlock height to allow dynamic resizing of content
            self.content_area.setMaximumHeight(16777215) # QWIDGETSIZE_MAX
            self.content_area.setMinimumHeight(0)
        else:
            self.content_area.setVisible(False)
        
        # Ensure the content area (scroll area) updates its geometry/size hint
        self.content_area.updateGeometry()
        # Trigger layout update
        self.updateGeometry()
        self.size_changed.emit()

    @Slot(bool)
    def on_checkbox_toggled(self, checked):
        self.toggled_enable.emit(checked)

    def setContentLayout(self, layout):
        widget = QWidget()
        widget.setLayout(layout)
        self.content_area.setWidget(widget)
        
        # Connect signals from child CollapsibleBoxes
        self._connect_child_signals(layout)

        # Initial setup
        widget.adjustSize()
        
        self.anim_max.setDuration(300)
        self.anim_max.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_min.setDuration(300)
        self.anim_min.setEasingCurve(QEasingCurve.InOutQuad)

    def _connect_child_signals(self, layout):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget():
                widget = item.widget()
                if isinstance(widget, CollapsibleBox):
                    widget.size_changed.connect(self.refresh_height)
                elif widget.layout():
                    self._connect_child_signals(widget.layout())
            elif item.layout():
                self._connect_child_signals(item.layout())

    @Slot()
    def refresh_height(self):
        # If we are expanded, we need to update our geometry to accommodate child changes
        if self.toggle_button.isChecked():
            self.content_area.widget().adjustSize()
            self.content_area.updateGeometry()
            self.updateGeometry()
            self.size_changed.emit()

    # --- Compatibility Methods ---
    
    def setTitle(self, title):
        self.title_label.setText(title)

    def setCheckable(self, checkable):
        pass 

    def setChecked(self, checked):
        if self.checkbox:
            self.checkbox.setChecked(checked)

    def isChecked(self):
        if self.checkbox:
            return self.checkbox.isChecked()
        return False

    def collapse(self):
        if self.toggle_button.isChecked():
            self.toggle_button.click()

    def expand(self):
        if not self.toggle_button.isChecked():
            self.toggle_button.click()
