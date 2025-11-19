from tasks.base_task import BaseTask

class ChestTask(BaseTask):
    @property
    def name(self):
        return "Chest"

    @property
    def priority(self):
        return 70

    def run_impl(self):
        self.logger.info("Executing Chest Task...")
        # TODO: Implement logic
        return True
