import time
from airtest.core.api import Template
from tasks.base_task import BaseTask
from i18n.i18n import get_text

class WarehouseTask(BaseTask):
    # UI 配置
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "lbl_enable", 
            "default": False,
            "menu": "Daily"
        }
    ]

    def __init__(self, device, data):
        super().__init__(device, data)
        # 资源定义
        self.IMG_GIFT = Template(r"assets/images/sidebar/gift.png", threshold=0.9)

    @property
    def name(self):
        return "WarehouseTask"

    @property
    def priority(self):
        return 10

    @property
    def default_interval(self):
        return 300 

    def run_impl(self):
        self.logger.info(get_text("log_warehouse_start"))
        
        # 1. 导航
        if not self.sidebar.switch_to_affairs_page():
            self.logger.warning(get_text("log_warehouse_nav_fail"))
            self._finish_and_wait(collapse=True) # 失败了还是要收起的
            return False

        # 2. 初始扫描
        self.logger.info("Scanning initial view...")
        if self._check_and_claim():
            return True

        # 3. 循环滑动查找
        for i in range(2):
            self.logger.info(f"Scrolling down ({i+1}/2)...")
            self.sidebar.scroll_up()
            if self._check_and_claim():
                return True

        # 4. 彻底没找到
        self.logger.info(get_text("log_warehouse_gift_not_found"))
        self._finish_and_wait(collapse=True) # 没找到也收起，保持整洁
        return True

    def _check_and_claim(self):
        """
        辅助方法：检查屏幕上是否有礼物并领取
        """
        pos = self.device.exists(self.IMG_GIFT)
        if pos:
            self.logger.info(get_text("log_warehouse_gift_found"))
            
            # 双击领取
            self.device.click(pos)
            time.sleep(0.4) 
            self.device.click(pos)
            
            self.logger.info(get_text("log_warehouse_claim_success"))
            
            # [修改] 成功领取后，传入 collapse=False，不收起侧边栏
            self._finish_and_wait(collapse=False)
            return True
        return False

    def _finish_and_wait(self, collapse=True):
        """
        统一的结束逻辑
        :param collapse: 是否收起侧边栏
        """
        self.set_next_run(seconds=300)
        
        if collapse:
            self.sidebar.collapse()
        else:
            # 如果不收起，也建议 Ensure Home 吗？
            # 不，根据你的要求 "成功就不需要 collapse"，隐含的意思是保留当前状态即可
            # 或者为了保险起见，可以只点一下主页键确保不在弹窗里，但不强制收侧边栏
            # 这里我们什么都不做，保留当前状态
            pass