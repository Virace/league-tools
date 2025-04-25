# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2025/4/26 3:15
# @Update  : 2025/4/26 3:15
# @Detail  : 

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class StringHash:
    """字符串哈希数据类"""
    string: str
    hash: int
    container_id: int = 0  # 容器ID，用于其他模块
    switch_id: int = 0  # 切换ID，用于其他模块
    sound_index: int = 0  # 声音索引，用于其他模块

    @staticmethod
    def dump_cls():
        """返回用于JSON序列化的编码器类"""

        class Encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, StringHash):
                    return obj.__dict__
                return json.JSONEncoder.default(self, obj)

        return Encoder

    def __eq__(self, other):
        if not isinstance(other, StringHash):
            return False
        return (self.string == other.string and
                self.hash == other.hash and
                self.container_id == other.container_id)

    def __hash__(self):
        return hash(f'{self.string}{self.hash}{self.container_id}')

    def __repr__(self):
        return (f'String: {self.string}, '
                f'Hash: {self.hash}, '
                f'Container_Id: {self.container_id}')


@dataclass
class EventData:
    """事件数据类"""
    category: str
    events: List[StringHash] = field(default_factory=list)
    bank_path: List[str] = field(default_factory=list)

    def __repr__(self):
        return (f'Category: {self.category}, '
                f'Bank_Paths: {len(self.bank_path)}, '
                f'Events: {len(self.events)}')


@dataclass
class MusicData:
    """音乐数据类"""
    theme_music_id: str = ""
    theme_music_transition_id: str = ""
    legacy_theme_music_id: str = ""
    legacy_theme_music_transition_id: str = ""
    victory_music_id: str = ""
    defeat_music_id: str = ""
    victory_banner_sound: str = ""
    defeat_banner_sound: str = ""
    ambient_event: str = ""
    # 存储未知字段，键为字段标记哈希，值为对应的数据
    unknown_fields: Dict[int, str] = field(default_factory=dict)

    def __repr__(self):
        base_info = (f'Theme Music: {self.theme_music_id}, '
                     f'Victory Music: {self.victory_music_id}, '
                     f'Defeat Music: {self.defeat_music_id}')
        if self.unknown_fields:
            base_info += f', Unknown Fields: {len(self.unknown_fields)}'
        return base_info


@dataclass
class AudioGroup:
    """
    音频组，包含一组银行单元和可选的音乐数据
    皮肤文件和非皮肤文件通用
    """
    bank_units: List[EventData] = field(default_factory=list)
    music: Optional[MusicData] = None

    def __repr__(self):
        events_count = sum(len(unit.events) for unit in self.bank_units)
        has_music = self.music is not None
        return f'Bank Units: {len(self.bank_units)} (Total Events: {events_count}), Has Music: {has_music}'
