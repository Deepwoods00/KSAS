# -*- coding: utf-8 -*-
from tasks.base_task import BaseTask
import time

class TestSidebarTask(BaseTask):
    @property
    def name(self):
        return "TestSidebarTask"

    @property
    def priority(self):
        return 100  # 高优先级，方便测试

    def run_impl(self):
        self.logger.info("=== 开始测试侧边栏功能 ===")
        
        # 1. 测试展开/收起 (get_idle_march_queues 内部会调用 expand)
        # self.sidebar.collapse() # 先收起一次，确保状态
        # time.sleep(1)

        # 2. 测试获取空闲队列
        self.logger.info("正在检测空闲行军队列...")
        idle_count = self.sidebar.get_idle_march_queues()
        
        self.logger.info(f"检测结果: 空闲队列数量 = {idle_count}")
        
        # 3. 验证数据持久化
        saved_count = self.data.get_stat("sidebar.idle_queues", -1)
        if saved_count == idle_count:
            self.logger.info(f"数据持久化验证成功: statistics.json 中已保存为 {saved_count}")
        else:
            self.logger.error(f"数据持久化验证失败: 内存值 {idle_count} != 保存值 {saved_count}")

        self.logger.info("=== 测试结束 ===")
        return True