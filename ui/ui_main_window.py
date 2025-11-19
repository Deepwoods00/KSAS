# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1000, 700)
        MainWindow.setStyleSheet(u"QMainWindow {\n"
"	background-color: #81D8D0; /* Tiffany Blue */\n"
"	color: #333333;\n"
"}\n"
"QWidget {\n"
"	font-family: \"Segoe UI\", \"Microsoft YaHei\";\n"
"	font-size: 10pt;\n"
"    color: #333333;\n"
"}\n"
"QListWidget {\n"
"	background-color: #E0F2F1; /* Lighter Teal/Cyan */\n"
"	border: none;\n"
"	color: #333333;\n"
"	outline: 0;\n"
"}\n"
"QListWidget::item {\n"
"	height: 40px;\n"
"	padding-left: 10px;\n"
"}\n"
"QListWidget::item:selected {\n"
"	background-color: #00897B; /* Darker Teal for selection */\n"
"	color: white;\n"
"}\n"
"QListWidget::item:hover {\n"
"	background-color: #B2DFDB;\n"
"}\n"
"QGroupBox {\n"
"	border: 1px solid #00897B;\n"
"	border-radius: 5px;\n"
"	margin-top: 20px;\n"
"	color: #00695C;\n"
"	font-weight: bold;\n"
"}\n"
"QGroupBox::title {\n"
"	subcontrol-origin: margin;\n"
"	left: 10px;\n"
"	padding: 0 3px 0 3px;\n"
"}\n"
"QPushButton {\n"
"	background-color: #E0F7FA;\n"
"	color: #006064;\n"
"	border: 1px solid #00897B;\n"
"	border-radius: 4px;\n"
"	padding: 5px 15px;\n"
"}\n"
""
                        "QPushButton:hover {\n"
"	background-color: #B2DFDB;\n"
"}\n"
"QPushButton:pressed {\n"
"	background-color: #80CBC4;\n"
"}\n"
"QPushButton#btn_toggle_running {\n"
"	background-color: #2e7d32; /* Default Green for Start */\n"
"    color: white;\n"
"	border-color: #1b5e20;\n"
"    font-weight: bold;\n"
"    font-size: 11pt;\n"
"}\n"
"QPushButton#btn_toggle_running:checked {\n"
"    background-color: #c62828; /* Red for Stop */\n"
"    border-color: #b71c1c;\n"
"}\n"
"QPushButton#btn_toggle_running:hover {\n"
"    opacity: 0.9;\n"
"}\n"
"QTabWidget::pane {\n"
"	border: 1px solid #00897B;\n"
"	background-color: #FFFFFF;\n"
"}\n"
"QTabBar::tab {\n"
"	background-color: #E0F2F1;\n"
"	color: #00695C;\n"
"	padding: 8px 20px;\n"
"	border-top-left-radius: 4px;\n"
"	border-top-right-radius: 4px;\n"
"}\n"
"QTabBar::tab:selected {\n"
"	background-color: #FFFFFF;\n"
"	color: #004D40;\n"
"	border-bottom: 2px solid #00897B;\n"
"}\n"
"QTextBrowser {\n"
"	background-color: #F0F4C3; /* Very light yellowish/green for logs, readable"
                        " */\n"
"	color: #33691E;\n"
"	border: 1px solid #00897B;\n"
"	font-family: \"Consolas\", \"Courier New\";\n"
"}\n"
"QComboBox {\n"
"	background-color: #E0F7FA;\n"
"	color: #006064;\n"
"	border: 1px solid #00897B;\n"
"	padding: 5px;\n"
"}\n"
"QComboBox::drop-down {\n"
"	border: 0px;\n"
"}\n"
"QLabel#label_logo {\n"
"    border: 2px dashed #00897B;\n"
"    color: #00796B;\n"
"}\n"
"")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout = QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_container = QWidget(self.centralwidget)
        self.sidebar_container.setObjectName(u"sidebar_container")
        self.sidebar_container.setMinimumSize(QSize(220, 0))
        self.sidebar_container.setMaximumSize(QSize(220, 16777215))
        self.sidebar_container.setStyleSheet(u"background-color: #B2DFDB; /* Sidebar slightly darker/different shade */")
        self.verticalLayout = QVBoxLayout(self.sidebar_container)
        self.verticalLayout.setSpacing(10)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 10, 0, 10)
        self.label_logo = QLabel(self.sidebar_container)
        self.label_logo.setObjectName(u"label_logo")
        self.label_logo.setMinimumSize(QSize(0, 100))
        self.label_logo.setStyleSheet(u"border: 2px dashed #00695C; color: #004D40; margin: 10px;")
        self.label_logo.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.label_logo)

        self.line = QFrame(self.sidebar_container)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line)

        self.list_instances = QListWidget(self.sidebar_container)
        self.list_instances.setObjectName(u"list_instances")
        self.list_instances.setSelectionMode(QAbstractItemView.SingleSelection)

        self.verticalLayout.addWidget(self.list_instances)

        self.sidebar_tools = QWidget(self.sidebar_container)
        self.sidebar_tools.setObjectName(u"sidebar_tools")
        self.verticalLayout_tools = QVBoxLayout(self.sidebar_tools)
        self.verticalLayout_tools.setObjectName(u"verticalLayout_tools")
        self.verticalLayout_tools.setContentsMargins(10, -1, 10, -1)
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.btn_add_instance = QPushButton(self.sidebar_tools)
        self.btn_add_instance.setObjectName(u"btn_add_instance")

        self.horizontalLayout_2.addWidget(self.btn_add_instance)

        self.btn_refresh_adb = QPushButton(self.sidebar_tools)
        self.btn_refresh_adb.setObjectName(u"btn_refresh_adb")

        self.horizontalLayout_2.addWidget(self.btn_refresh_adb)

        self.btn_global_settings = QPushButton(self.sidebar_tools)
        self.btn_global_settings.setObjectName(u"btn_global_settings")

        self.horizontalLayout_2.addWidget(self.btn_global_settings)


        self.verticalLayout_tools.addLayout(self.horizontalLayout_2)


        self.verticalLayout.addWidget(self.sidebar_tools)


        self.horizontalLayout.addWidget(self.sidebar_container)

        self.stacked_pages = QStackedWidget(self.centralwidget)
        self.stacked_pages.setObjectName(u"stacked_pages")
        self.page_welcome = QWidget()
        self.page_welcome.setObjectName(u"page_welcome")
        self.verticalLayout_2 = QVBoxLayout(self.page_welcome)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.label_welcome = QLabel(self.page_welcome)
        self.label_welcome.setObjectName(u"label_welcome")
        font = QFont()
        font.setPointSize(16)
        self.label_welcome.setFont(font)
        self.label_welcome.setStyleSheet(u"color: #004D40;")
        self.label_welcome.setAlignment(Qt.AlignCenter)

        self.verticalLayout_2.addWidget(self.label_welcome)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer_2)

        self.stacked_pages.addWidget(self.page_welcome)
        self.page_instance_detail = QWidget()
        self.page_instance_detail.setObjectName(u"page_instance_detail")
        self.verticalLayout_3 = QVBoxLayout(self.page_instance_detail)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.header_frame = QFrame(self.page_instance_detail)
        self.header_frame.setObjectName(u"header_frame")
        self.header_frame.setFrameShape(QFrame.StyledPanel)
        self.header_frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.header_frame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_instance_name = QLabel(self.header_frame)
        self.label_instance_name.setObjectName(u"label_instance_name")
        font1 = QFont()
        font1.setPointSize(14)
        font1.setBold(True)
        self.label_instance_name.setFont(font1)

        self.horizontalLayout_3.addWidget(self.label_instance_name)

        self.label_status_icon = QLabel(self.header_frame)
        self.label_status_icon.setObjectName(u"label_status_icon")

        self.horizontalLayout_3.addWidget(self.label_status_icon)

        self.label_status_text = QLabel(self.header_frame)
        self.label_status_text.setObjectName(u"label_status_text")

        self.horizontalLayout_3.addWidget(self.label_status_text)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.btn_toggle_running = QPushButton(self.header_frame)
        self.btn_toggle_running.setObjectName(u"btn_toggle_running")
        self.btn_toggle_running.setMinimumSize(QSize(120, 40))
        self.btn_toggle_running.setCheckable(True)

        self.horizontalLayout_3.addWidget(self.btn_toggle_running)


        self.verticalLayout_3.addWidget(self.header_frame)

        self.tabWidget = QTabWidget(self.page_instance_detail)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab_tasks = QWidget()
        self.tab_tasks.setObjectName(u"tab_tasks")
        self.verticalLayout_4 = QVBoxLayout(self.tab_tasks)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.scrollArea = QScrollArea(self.tab_tasks)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 736, 515))
        self.verticalLayout_tasks = QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_tasks.setObjectName(u"verticalLayout_tasks")
        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_tasks.addItem(self.verticalSpacer_3)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayout_4.addWidget(self.scrollArea)

        self.tabWidget.addTab(self.tab_tasks, "")
        self.tab_logs = QWidget()
        self.tab_logs.setObjectName(u"tab_logs")
        self.verticalLayout_5 = QVBoxLayout(self.tab_logs)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.text_log = QTextBrowser(self.tab_logs)
        self.text_log.setObjectName(u"text_log")

        self.verticalLayout_5.addWidget(self.text_log)

        self.tabWidget.addTab(self.tab_logs, "")
        self.tab_stats = QWidget()
        self.tab_stats.setObjectName(u"tab_stats")
        self.tabWidget.addTab(self.tab_stats, "")

        self.verticalLayout_3.addWidget(self.tabWidget)

        self.stacked_pages.addWidget(self.page_instance_detail)

        self.horizontalLayout.addWidget(self.stacked_pages)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.stacked_pages.setCurrentIndex(0)
        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"KSAS V3.4 - Kingshot Automation System", None))
        self.label_logo.setText(QCoreApplication.translate("MainWindow", u"LOGO\n"
"(Square)", None))
#if QT_CONFIG(tooltip)
        self.btn_add_instance.setToolTip(QCoreApplication.translate("MainWindow", u"\u6dfb\u52a0\u65b0\u8bbe\u5907", None))
#endif // QT_CONFIG(tooltip)
        self.btn_add_instance.setText(QCoreApplication.translate("MainWindow", u"\u2795", None))
#if QT_CONFIG(tooltip)
        self.btn_refresh_adb.setToolTip(QCoreApplication.translate("MainWindow", u"\u5237\u65b0 ADB \u8fde\u63a5", None))
#endif // QT_CONFIG(tooltip)
        self.btn_refresh_adb.setText(QCoreApplication.translate("MainWindow", u"\ud83d\udd04", None))
#if QT_CONFIG(tooltip)
        self.btn_global_settings.setToolTip(QCoreApplication.translate("MainWindow", u"\u5168\u5c40\u8bbe\u7f6e", None))
#endif // QT_CONFIG(tooltip)
        self.btn_global_settings.setText(QCoreApplication.translate("MainWindow", u"\u2699\ufe0f", None))
        self.label_welcome.setText(QCoreApplication.translate("MainWindow", u"\u8bf7\u4ece\u5de6\u4fa7\u9009\u62e9\u4e00\u4e2a\u5b9e\u4f8b\uff0c\u6216\u70b9\u51fb \u2795 \u6dfb\u52a0\u65b0\u8bbe\u5907", None))
        self.label_instance_name.setText(QCoreApplication.translate("MainWindow", u"Instance Name", None))
        self.label_status_icon.setText(QCoreApplication.translate("MainWindow", u"\ud83d\udfe2", None))
        self.label_status_text.setText(QCoreApplication.translate("MainWindow", u"Online - Idle", None))
        self.btn_toggle_running.setText(QCoreApplication.translate("MainWindow", u"\u25b6 \u542f\u52a8\u6302\u673a", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_tasks), QCoreApplication.translate("MainWindow", u"\u4efb\u52a1\u914d\u7f6e", None))
        self.text_log.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:'Consolas'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" color:#888888;\">[12:00:00] System initialized.</span></p>\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" color:#00897B;\">[12:00:01] Connected to device.</span></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_logs), QCoreApplication.translate("MainWindow", u"\u8fd0\u884c\u65e5\u5fd7", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_stats), QCoreApplication.translate("MainWindow", u"\u7edf\u8ba1\u4e0e\u72b6\u6001", None))
    # retranslateUi

