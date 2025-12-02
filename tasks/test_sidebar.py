# -*- coding: utf-8 -*-
from tasks.base_task import BaseTask
from i18n.i18n import get_text
import time

class TestSidebarTask(BaseTask):
    @property
    def name(self):
        return "TestSidebarTask"

    @property
    def priority(self):
        return 100  # 高优先级，方便测试

    def run_impl(self):
        self.logger.info(get_text("log_test_sidebar_start"))
        
        # 1. 测试展开/收起 (get_idle_march_queues 内部会调用 expand)
        # self.sidebar.collapse() # 先收起一次，确保状态
        # time.sleep(1)

        # 2. 测试获取空闲队列
        self.logger.info(get_text("log_checking_idle_queues"))
        idle_count = self.sidebar.get_idle_march_queues()
        
        self.logger.info(get_text("log_idle_queues_result", idle_count))
        
        # 3. 验证数据持久化
        saved_count = self.data.get_stat("sidebar.idle_queues", -1)
        if saved_count == idle_count:
            self.logger.info(get_text("log_persistence_success", saved_count))
        else:
            self.logger.error(get_text("log_persistence_failed", idle_count, saved_count))

        self.logger.info(get_text("log_test_sidebar_end"))
        return True