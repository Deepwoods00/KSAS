from tasks.base_task import BaseTask
from airtest.core.api import Template
from i18n.i18n import get_text

class CombatTask(BaseTask):
    """
    战斗任务基类
    处理通用的编队、选将、调兵逻辑
    """

    # 戴安娜减耗表 (技能等级: (集结体力, 打野体力))
    DIANA_COST_TABLE = {
        1: (23, 9),
        2: (22, 9),
        3: (22, 9),
        4: (21, 9),
        5: (20, 8)
    }
    DEFAULT_COST = (25, 10)

    def __init__(self, device, data):
        super().__init__(device, data)
        self.target_heroes = []
        self.soldier_count = 0

    def calculate_cost(self, mode="rally"):
        skill_level = self.data.get_cfg("modules.general.diana_level", 0)
        if skill_level == 0:
            return self.DEFAULT_COST[0] if mode == "rally" else self.DEFAULT_COST[1]

        if self.find_diana():
            costs = self.DIANA_COST_TABLE.get(skill_level, self.DEFAULT_COST)
            cost = costs[0] if mode == "rally" else costs[1]
            self.logger.info(get_text("log_diana_cost", skill_level, cost))
            return cost
        else:
            cost = self.DEFAULT_COST[0] if mode == "rally" else self.DEFAULT_COST[1]
            self.logger.info(get_text("log_normal_cost", cost))
            return cost

    def find_diana(self):
        # 确保路径正确
        img_diana = Template(r"assets/images/heroes/diana.png", threshold=0.9)
        return self.device.exists(img_diana)

    def select_heroes(self, heroes: list):
        """
        根据传入的英雄列表进行选将
        :param heroes: list, 英雄名称列表 (e.g. ['diana', 'jessie'])
        """
        # TODO: Implement hero selection logic
        pass

    def adjust_soldiers(self, count: int):
        """
        调整士兵数量
        :param count: int, 目标兵力值
        """
        # TODO: Implement soldier adjustment logic
        pass

    def verify_attack_success(self):
        """
        验证出击是否成功
        :return: bool
        """
        # TODO: Implement attack verification logic
        return True