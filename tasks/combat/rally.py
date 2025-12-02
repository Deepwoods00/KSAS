from tasks.base_task import BaseTask
from i18n.i18n import get_text

class RallyTask(BaseTask):
    config_schema = [
        {
            "key": "enable",
            "type": "checkbox",
            "label": "Enable Rally Task",
            "default": False,
            "menu": "Combat"
        }
    ]

    @property
    def name(self):
        return "Rally"

    @property
    def priority(self):
        return 45

    def run_impl(self):
        self.logger.info(get_text("log_rally_task_start"))
        # TODO: Implement logic
        return True
