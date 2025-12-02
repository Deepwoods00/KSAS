from tasks.base_task import BaseTask
from i18n.i18n import get_text

class GatherTask(BaseTask):
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Gather Task",
            "default": False,
            "menu": "Daily"
        }
    ]

    @property
    def name(self):
        return "Gather"

    @property
    def priority(self):
        return 80

    def run_impl(self):
        self.logger.info(get_text("log_gather_task_start"))
        # TODO: Implement logic
        return True
