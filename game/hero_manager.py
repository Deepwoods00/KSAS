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

    def update_hero_status(self, hero_name, owned=None, state=None):
        """
        更新英雄状态
        :param hero_name: 英雄代号 (必须在 HERO_LIST 中)
        :param owned: bool, 是否拥有 (None 表示不更新此项) -> 存入 config
        :param state: str, 状态 "idle" / "busy" (None 表示不更新此项) -> 存入 stats
        """
        if hero_name not in self.HERO_LIST:
            return

        # 1. 更新拥有状态 (Config)
        if owned is not None:
            self.data.set_cfg(f"heroes.{hero_name}", owned)
        
        # 2. 更新状态信息 (Stats)
        if state is not None:
            self.data.set_stat(f"heroes.{hero_name}", state)

    def get_hero_info(self, hero_name):
        """
        获取单个英雄的完整信息
        :return: dict { "owned": bool, "state": str }
        """
        # 拥有状态从 config 读取
        owned = self.data.get_cfg(f"heroes.{hero_name}", False)
        # 状态信息从 stats 读取
        state = self.data.get_stat(f"heroes.{hero_name}", "idle")
        
        return {"owned": owned, "state": state}

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

    def get_heroes_by_state(self, target_state="idle"):
        """
        获取指定状态的英雄列表
        :param target_state: "idle" or "busy"
        :return: list [hero_name, ...]
        """
        # 从 stats 读取所有英雄状态信息
        all_heroes_stats = self.data.get_stat("heroes", {})
        result = []
        for name, state in all_heroes_stats.items():
            if state == target_state:
                result.append(name)
        return result

    def is_hero_available(self, hero_name):
        """
        检查英雄是否可用 (已拥有且空闲)
        """
        info = self.get_hero_info(hero_name)
        # 拥有且状态为空闲
        return info.get("owned", False) and (info.get("state") == "idle")