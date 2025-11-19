# tasks/task_registry.py

# 1. 引入你所有的任务类
from tasks.example_task import ExampleTask
from tasks.combat.beast import BeastTask
from tasks.combat.rally import RallyTask
from tasks.daily.intel import IntelTask
from tasks.daily.chest import ChestTask
from tasks.daily.gather import GatherTask
from tasks.shop.general_shop import ShopTask
from tasks.daily.stamina_check import StaminaCheckTask

# 2. 把它们放进一个列表
TASK_CLASSES = [
    # ExampleTask, # 示例任务可以先注释掉
    BeastTask,
    RallyTask,
    IntelTask,
    ChestTask,
    GatherTask,
    ShopTask,
    StaminaCheckTask,
]

def get_all_tasks():
    return TASK_CLASSES