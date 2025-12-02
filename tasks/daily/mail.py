from tasks.base_task import BaseTask
from airtest.core.api import Template
from i18n.i18n import get_text
import time

class MailTask(BaseTask):
    # 配置 Schema (用于元数据，实际 UI 由 Widget 控制)
    config_schema = [
        {
            "key": "enable", 
            "type": "checkbox", 
            "default": False,
            "menu": "Daily"  # <--- 【关键修改】加上这一行，告诉 UI 把它放在“日常”里
        },
        {"key": "collect_system", "default": True},
        {"key": "collect_alliance", "default": True},
        {"key": "collect_report", "default": False},
        {"key": "collect_war", "default": False}
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        # 资源: 主页邮件图标
        self.IMG_MAIL = Template(r"assets/images/home/mail.png", threshold=0.9)
        
        # 坐标定义 (x, y)
        self.POS_Categories = {
            "war": (118, 123),      # 战争信息
            "alliance": (194, 111), # 联盟信息
            "system": (391, 114),   # 系统信息
            "report": (466, 121)    # 报告
        }
        self.POS_CLAIM = (600, 1230) # 一键领取

    @property
    def name(self):
        return "MailTask"

    @property
    def priority(self):
        return 60

    @property
    def default_interval(self):
        return 3600 # 默认1小时

    def run_impl(self):
        # Log: 开始收取邮件
        self.logger.info(get_text("log_mail_start"))

        # 1. Ensure Home
        self.device.ensure_home()
        
        # 2. 搜索并点击 Mail 图标
        if self.device.exists(self.IMG_MAIL):
            # Log: 点击邮件图标
            self.logger.info(get_text("log_mail_click_icon"))
            self.device.click(self.IMG_MAIL)
            self.device.sleep(0.5) # 等待打开
        else:
            # Log: 未找到邮件图标
            self.logger.warning(get_text("log_mail_icon_missing"))
            return False

        # 3. 定义遍历列表 (配置键, 内部键, 翻译键)
        # 翻译键对应 yaml 中的文本，例如 cfg_mail_system="系统信息"
        check_list = [
            ("collect_system", "system", "cfg_mail_system"),
            ("collect_alliance", "alliance", "cfg_mail_alliance"),
            ("collect_report", "report", "cfg_mail_report"),
            ("collect_war", "war", "cfg_mail_war")
        ]

        # 4. 循环处理
        for cfg_key, cat_key, i18n_key in check_list:
            # 获取显示名称 (用于日志)
            display_name = get_text(i18n_key)
            
            # 检查配置是否启用
            if self.data.get_cfg(f"modules.mailtask.{cfg_key}", False):
                # Log: 正在处理: 系统信息
                self.logger.info(get_text("log_mail_process_cat", display_name))
                self.process_category(cat_key)
            else:
                # Log: 跳过: 系统信息 (未启用)
                self.logger.info(get_text("log_mail_skip_cat", display_name))

        # 5. 结束
        self.device.ensure_home()
        # Log: 邮件收取完成
        self.logger.info(get_text("log_mail_finish"))
        return True

    def process_category(self, category_key):
        """处理单个频道的逻辑"""
        cat_pos = self.POS_Categories.get(category_key)
        if not cat_pos: return

        # 动作 1: 点击页面两次，间隔 0.4s
        # 注意：使用 device.click 单次点击 + sleep 确保间隔准确
        self.device.click(cat_pos)
        time.sleep(0.4)
        self.device.click(cat_pos)
        
        # 等待界面响应
        time.sleep(0.5)

        # 动作 2: 点击一键领取两次，间隔 0.4s
        self.device.click(self.POS_CLAIM)
        time.sleep(0.4)
        self.device.click(self.POS_CLAIM)

        # 等待弹窗或动画
        time.sleep(0.5)