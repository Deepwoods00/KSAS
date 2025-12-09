# tasks/task_registry.py

# 1. 引入你所有的任务类
from tasks.example_task import ExampleTask
from tasks.combat.beast import BeastTask
from tasks.combat.wolf import WolfTask
from tasks.combat.terror import RallyTask
from tasks.daily.intel import IntelTask
from tasks.daily.gather import GatherTask
from tasks.shop.general_shop import ShopTask
from tasks.test_sidebar import TestSidebarTask
from tasks.daily.alliance import AllianceTechTask, AllianceChestTask, AllianceHelpTask
from tasks.daily.mail import MailTask
from tasks.daily.stamina_control import StaminaControlTask
from tasks.daily.warehouse import WarehouseTask
from tasks.daily.recruit_adv import RecruitAdvTask
from tasks.daily.recruit_epic import RecruitEpicTask
from tasks.daily.training import TroopTrainingTask
from tasks.daily.vip_chest import VipChestTask 

# 2. 把它们放进一个列表
TASK_CLASSES = [
    # TestSidebarTask, # 测试任务放最前面方便找
    # ExampleTask, # 示例任务可以先注释掉
    StaminaControlTask, 
    BeastTask,
    WolfTask,
    RallyTask,
    IntelTask,
    # GatherTask,
    # ShopTask,
    AllianceTechTask,
    AllianceChestTask,
    AllianceHelpTask,
    MailTask,
    WarehouseTask,
    RecruitAdvTask,
    RecruitEpicTask,
    TroopTrainingTask, 
    VipChestTask,
]

def get_all_tasks():
    return TASK_CLASSES