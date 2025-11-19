from tasks.base_task import BaseTask

class ShopTask(BaseTask):
    @property
    def name(self):
        return "Shop"

    @property
    def priority(self):
        return 90

    def run_impl(self):
        self.logger.info("Executing Shop Task...")
        # TODO: Implement logic
        return True
