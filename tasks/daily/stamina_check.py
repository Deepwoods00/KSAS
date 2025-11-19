# tasks/daily/stamina_check.py
from tasks.base_task import BaseTask

class StaminaCheckTask(BaseTask):
    @property
    def name(self):
        return "StaminaCheckTask"

    @property
    def priority(self):
        return 10  # 高优先级，方便测试

    def run_impl(self):
        # 直接调用基类的 get_current_stamina 方法
        val = self.get_current_stamina()
        self.logger.info(f"手动检测体力完成: {val}")
        return True
