# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2023/5/15 19:21
# @Update  : 2025/5/1 2:34
# @Detail  : HIRC区块数据类

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional


class HIRCType(IntEnum):
    """HIRC对象类型枚举"""
    # STATE = 1
    SOUND = 2
    ACTION = 3
    EVENT = 4
    RANDOM_CONTAINER = 5
    SWITCH_CONTAINER = 6
    # ACTOR_MIXER = 7
    # BUS = 8
    # LAYER_CONTAINER = 9
    MUSIC_SEGMENT_CONTAINER = 10
    MUSIC_TRACK = 11
    MUSIC_SWITCH_CONTAINER = 12
    MUSIC_RANDOM_CONTAINER = 13


@dataclass
class Sound:
    """
    声音对象类 0x02 [Sound]
    """
    object_id: int
    source_id: int
    stream_type: int
        


@dataclass
class Action:
    """
    动作对象类 0x03 [Action]
    根据action_type的不同，有不同的属性
    0x1901 [SetSwitch]
        switch_group_id: int
        switch_state_id: int
    
    0x1204 [SetState]
        state_group_id: int
        target_state_id: int
    
    其余类型
        id_ext: int

    """
    object_id: int
    action_type: int
    id_ext: Optional[int]
    switch_group_id: Optional[int]
    switch_state_id: Optional[int]
    state_group_id: Optional[int]
    target_state_id: Optional[int]



@dataclass
class Event:
    """
    事件对象类 0x04 [Event]
    """
    object_id: int
    event_ids: List[int]


@dataclass
class RanSeqCntr:
    """
    随机序列容器类 0x05 [Random/Sequence Container]
    
    属性:
        object_id: 对象ID
        direct_parent_id: 直接父对象ID
        child_ids: 子对象ID列表
    """
    object_id: int
    direct_parent_id: Optional[int]
    child_ids: List[int]


@dataclass
class SwitchCntr:
    """
    切换容器类 0x06 [Switch Container]
    
    属性:
        object_id: 对象ID
        direct_parent_id: 直接父对象ID
        child_ids: 子对象ID列表
    """
    object_id: int
    direct_parent_id: Optional[int]
    child_ids: List[int]


@dataclass
class MusicSegmentCntr:
    """
    音乐段容器类 0x0A [Music Segment]
    
    属性:
        object_id: 对象ID
        direct_parent_id: 直接父对象ID
        child_ids: 子对象ID列表
    
    这个类型在原生 HIRC 中会继续递归 child_ids
    """
    object_id: int
    direct_parent_id: Optional[int]
    child_ids: List[int]


@dataclass
class MusicTrack:
    """
    音乐轨道类 0x0B [Music Track]
    
    属性:
        object_id: 对象ID
        source_id: 音频源ID
    
    file_ids 直接对应 wemId
    """
    object_id: int
    file_ids: List[int]


@dataclass
class MusicSwitchCntr:
    """
    音乐切换容器类 0x0C [Music Switch]
    
    属性:
        object_id: 对象ID
        direct_parent_id: 直接父对象ID
        child_ids: 子对象ID列表
    这个类型在原生 HIRC 中会继续递归 child_ids
    """
    object_id: int
    direct_parent_id: Optional[int]
    child_ids: List[int]


@dataclass
class MusicRandomCntr:
    """
    音乐随机容器类 0x0D [Music Random/Sequence]
    
    属性:
        object_id: 对象ID
        direct_parent_id: 直接父对象ID
        child_ids: 子对象ID列表
    这里对应 music playlist/random container
    """
    object_id: int
    direct_parent_id: Optional[int]
    child_ids: List[int]
