# tasks/example_task.py
import time
from tasks.base_task import BaseTask

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
        self.logger.info(">>> ExampleTask 开始执行！正在模拟点击...")
        time.sleep(2) # 假装在点屏幕
        self.logger.info(">>> 点击完成，正在识别...")
        time.sleep(1) # 假装在 OCR
        self.logger.info(">>> 任务完成！")
        return True