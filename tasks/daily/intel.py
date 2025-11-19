from tasks.base_task import BaseTask

class IntelTask(BaseTask):
    @property
    def name(self):
        return "Intel"

    @property
    def priority(self):
        return 60

    def run_impl(self):
        self.logger.info("Executing Intel Task...")
        # TODO: Implement logic
        return True
