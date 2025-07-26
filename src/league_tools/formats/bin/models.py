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
from typing import Dict, List, Optional


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
        return (
            self.string == other.string
            and self.hash == other.hash
            and self.container_id == other.container_id
        )

    def __hash__(self):
        return hash(f"{self.string}{self.hash}{self.container_id}")

    def __repr__(self):
        return (
            f"String: {self.string}, "
            f"Hash: {self.hash}, "
            f"Container_Id: {self.container_id}"
        )


@dataclass
class EventData:
    """事件数据类"""

    category: str
    events: List[StringHash] = field(default_factory=list)
    bank_path: List[str] = field(default_factory=list)

    @staticmethod
    def dump_cls():
        """返回用于JSON序列化的编码器类"""

        class Encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, EventData):
                    result = obj.__dict__.copy()
                    result["events"] = [event.__dict__ for event in obj.events]
                    return result
                return json.JSONEncoder.default(self, obj)

        return Encoder

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "category": self.category,
            "events": [event.__dict__ for event in self.events],
            "bank_path": self.bank_path,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "EventData":
        """从字典创建对象"""
        events = [StringHash(**event_data) for event_data in data.get("events", [])]
        return cls(
            category=data.get("category", ""),
            events=events,
            bank_path=data.get("bank_path", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "EventData":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __repr__(self):
        return (
            f"Category: {self.category}, "
            f"Bank_Paths: {len(self.bank_path)}, "
            f"Events: {len(self.events)}"
        )


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

    @staticmethod
    def dump_cls():
        """返回用于JSON序列化的编码器类"""

        class Encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, MusicData):
                    result = obj.__dict__.copy()
                    # 转换unknown_fields中的整数键为字符串
                    result["unknown_fields"] = {
                        str(k): v for k, v in obj.unknown_fields.items()
                    }
                    return result
                return json.JSONEncoder.default(self, obj)

        return Encoder

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {k: v for k, v in self.__dict__.items() if k != "unknown_fields"}
        # 转换整数键为字符串
        result["unknown_fields"] = {str(k): v for k, v in self.unknown_fields.items()}
        return result

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "MusicData":
        """从字典创建对象"""
        # 复制数据以避免修改原始字典
        data_copy = data.copy()
        # 处理unknown_fields，将字符串键转回整数
        if "unknown_fields" in data_copy:
            unknown_fields = {int(k): v for k, v in data_copy["unknown_fields"].items()}
            data_copy["unknown_fields"] = unknown_fields
        return cls(**data_copy)

    @classmethod
    def from_json(cls, json_str: str) -> "MusicData":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __repr__(self):
        base_info = (
            f"Theme Music: {self.theme_music_id}, "
            f"Victory Music: {self.victory_music_id}, "
            f"Defeat Music: {self.defeat_music_id}"
        )
        if self.unknown_fields:
            base_info += f", Unknown Fields: {len(self.unknown_fields)}"
        return base_info


@dataclass
class AudioGroup:
    """
    音频组，包含一组银行单元和可选的音乐数据
    皮肤文件和非皮肤文件通用
    """

    bank_units: List[EventData] = field(default_factory=list)
    music: Optional[MusicData] = None

    @staticmethod
    def dump_cls():
        """返回用于JSON序列化的编码器类"""

        class Encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, AudioGroup):
                    result = {
                        "bank_units": [
                            bank_unit.__dict__ for bank_unit in obj.bank_units
                        ],
                    }
                    if obj.music:
                        result["music"] = obj.music.__dict__
                    return result
                return json.JSONEncoder.default(self, obj)

        return Encoder

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "bank_units": [bank_unit.to_dict() for bank_unit in self.bank_units],
        }
        if self.music:
            result["music"] = self.music.to_dict()
        return result

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), cls=self.dump_cls(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "AudioGroup":
        """从字典创建对象"""
        bank_units = [
            EventData.from_dict(unit_data) for unit_data in data.get("bank_units", [])
        ]
        music = None
        if "music" in data and data["music"]:
            music = MusicData.from_dict(data["music"])

        return cls(bank_units=bank_units, music=music)

    @classmethod
    def from_json(cls, json_str: str) -> "AudioGroup":
        """从JSON字符串创建对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __repr__(self):
        events_count = sum(len(unit.events) for unit in self.bank_units)
        has_music = self.music is not None
        return f"Bank Units: {len(self.bank_units)} (Total Events: {events_count}), Has Music: {has_music}"
