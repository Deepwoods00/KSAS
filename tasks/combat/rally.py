from tasks.base_task import BaseTask

class RallyTask(BaseTask):
    @property
    def name(self):
        return "Rally"

    @property
    def priority(self):
        return 45

    def run_impl(self):
        self.logger.info("Executing Rally Task...")
        # TODO: Implement logic
        return True
