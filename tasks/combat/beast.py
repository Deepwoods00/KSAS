from tasks.base_task import BaseTask

class BeastTask(BaseTask):
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Beast Task",
            "default": False,
            "menu": "Combat"
        }
    ]

    @property
    def name(self):
        return "BeastTask"

    @property
    def priority(self):
        return 40

    def run_impl(self):
        self.logger.info("Executing Beast Task...")
        # 测试调级功能：比如调到 5级
        self.select_search_level(5)
        return True
