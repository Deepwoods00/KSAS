# tasks/example_task.py
import time
from tasks.base_task import BaseTask
from i18n.i18n import get_text

class ExampleTask(BaseTask):
    @property
    def name(self):
        return "ExampleTask"

    @property
    def priority(self):
        return 10 # 优先级

    @property
    def default_interval(self):
        return 60 # 默认每 60 秒跑一次

    def run_impl(self):
        """
        模拟干活
        """
        self.logger.info(get_text("log_example_task_start"))
        time.sleep(2) # 假装在点屏幕
        self.logger.info(get_text("log_example_task_clicking"))
        time.sleep(1) # 假装在 OCR
        self.logger.info(get_text("log_example_task_finished"))
        return True