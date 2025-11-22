# -*- coding: utf-8 -*-

class HeroManager:
    """
    英雄状态管理器
    负责管理英雄的拥有状态、出击队伍信息，并与 DataStore 进行同步。
    """

    # 英雄白名单
    # 格式: 内部代号 (小写)
    HERO_LIST = [
        # Gen 4
        "rosa", "alcar", "margot",
        # Gen 3
        "jaeger", "eric", "petra",
        # Gen 2
        "hilde", "zoe", "marlin",
        # Gen 1
        "jabel", "amadeus", "helga", "saul",
        # SR (Epic)
        "amane", "yeonwoo", "fahd", "chenko", "gordon", "diana", "howard", "quinn",
        # R (Rare)
        "olive", "edwin", "seth", "forrest",
    ]

    def __init__(self, data):
        """
        :param data: InstanceDataStore 实例
        """
        self.data = data

    def update_hero_status(self, hero_name, owned=None, queue_index=None):
        """
        更新英雄状态
        :param hero_name: 英雄代号 (必须在 HERO_LIST 中)
        :param owned: bool, 是否拥有 (None 表示不更新此项) -> 存入 config
        :param queue_index: int, 所在队列编号 (None 表示不更新此项, 0 表示不在任何队列) -> 存入 stats
        """
        if hero_name not in self.HERO_LIST:
            return

        # 1. 更新拥有状态 (Config)
        if owned is not None:
            self.data.set_cfg(f"heroes.{hero_name}", owned)
        
        # 2. 更新队列信息 (Stats)
        if queue_index is not None:
            self.data.set_stat(f"heroes.{hero_name}", queue_index)

    def get_hero_info(self, hero_name):
        """
        获取单个英雄的完整信息
        :return: dict { "owned": bool, "queue": int/None }
        """
        # 拥有状态从 config 读取
        owned = self.data.get_cfg(f"heroes.{hero_name}", False)
        # 队列信息从 stats 读取
        queue = self.data.get_stat(f"heroes.{hero_name}", 0)
        
        return {"owned": owned, "queue": queue}

    def get_owned_heroes(self):
        """
        获取所有已拥有的英雄列表
        :return: list [hero_name, ...]
        """
        # 从 config 读取所有英雄配置
        all_heroes_cfg = self.data.get_cfg("heroes", {})
        owned_list = []
        for name, is_owned in all_heroes_cfg.items():
            if is_owned:
                owned_list.append(name)
        return owned_list

    def get_heroes_in_queue(self, queue_index):
        """
        获取指定队列中的英雄列表
        :param queue_index: 队列编号
        :return: list [hero_name, ...]
        """
        # 从 stats 读取所有英雄队列信息
        all_heroes_stats = self.data.get_stat("heroes", {})
        in_queue = []
        for name, q_idx in all_heroes_stats.items():
            if q_idx == queue_index:
                in_queue.append(name)
        return in_queue

    def is_hero_available(self, hero_name):
        """
        检查英雄是否可用 (已拥有且不在任何队列中)
        """
        info = self.get_hero_info(hero_name)
        # 拥有且队列为0(空闲)
        return info.get("owned", False) and (info.get("queue") == 0)