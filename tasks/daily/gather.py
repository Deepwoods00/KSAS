from tasks.base_task import BaseTask

class GatherTask(BaseTask):
    @property
    def name(self):
        return "Gather"

    @property
    def priority(self):
        return 80

    def run_impl(self):
        self.logger.info("Executing Gather Task...")
        # TODO: Implement logic
        return True
