# tasks/task_registry.py

# 1. 引入你所有的任务类
from tasks.example_task import ExampleTask
# 以后有了 HuntingTask 就在这里加: from tasks.hunting import HuntingTask

# 2. 把它们放进一个列表
TASK_CLASSES = [
    ExampleTask,
    # HuntingTask,
]

def get_all_tasks():
    return TASK_CLASSES