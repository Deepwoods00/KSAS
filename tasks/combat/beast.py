from tasks.base_task import BaseTask

class BeastTask(BaseTask):
    @property
    def name(self):
        return "Beast"

    @property
    def priority(self):
        return 40

    def run_impl(self):
        self.logger.info("Executing Beast Task...")
        # TODO: Implement logic
        return True
