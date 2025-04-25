# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 13:14
# @Update  : 2025/4/27 0:30
# @Detail  : 英雄联盟皮肤Bin文件解析(提取语音触发事件名称与音乐数据)

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from loguru import logger

from src.league_tools.base import SectionNoId

# 文件头标记
HEADER_SIGNATURE = b'PROP'

# 主要结构类型哈希
SKIN_AUDIO_PROPERTIES = 0x8F7B194F  # 皮肤音频属性
MUSIC = 0x9f9c4fd4  # 音乐结构标记
MUSIC_AUDIO_DATA_PROPERTIES = 0x6630947b  # 音乐音频数据属性
THEME_MUSIC = 0x53ad3c01  # 主题音乐标记(皮肤文件特有)

# 银行单元相关标记
BANK_UNITS_SIGNATURE = [0x92, 0x9F, 0xF2, 0xF8]  # 银行单元集合标记
BANK_UNIT_SIGNATURE = 0xA4416515  # 银行单元标记

# 字段标记
NAME_SIGNATURE = 0x8D39BDE6  # 名称标记
BANK_PATH_SIGNATURE = 0x2A21AD00  # 银行路径标记
EVENTS_SIGNATURE = 0x12D8E384  # 事件标记
VOICE_OVER_SIGNATURE = 0x3B13AA4B  # 语音覆盖标记
ASYNCHRONE_SIGNATURE = 0xA8A558FF
TAG_EVENT_LIST = 0xD65BAC4D  # 标签事件列表

# 音乐结构字段哈希
THEME_MUSIC_ID = 0xEDA78F54  # 主题音乐ID
THEME_MUSIC_TRANSITION_ID = 0x8CD28ECB  # 主题音乐过渡ID
LEGACY_THEME_MUSIC_ID = 0xECC0E697  # 传统主题音乐ID
LEGACY_THEME_MUSIC_TRANSITION_ID = 0x4FD5971C  # 传统主题音乐过渡ID
VICTORY_MUSIC_ID = 0xD25DA809  # 胜利音乐ID
DEFEAT_MUSIC_ID = 0x47F3FB40  # 失败音乐ID
VICTORY_BANNER_SOUND = 0x73F9C3E6  # 胜利横幅音效
DEFEAT_BANNER_SOUND = 0x27F7A183  # 失败横幅音效
AMBIENT_EVENT = 0x3FDA1A59  # 环境事件

# 类型常量
TYPE_STRING = 0x10
TYPE_BOOL = 0x01
TYPE_CONTAINER = 0x12


def str_fnv_32(name: str) -> int:
    """
    计算字符串的FNV-1a 32位哈希值

    :param name: 要计算哈希的字符串
    :return: 32位哈希值
    """
    h = 0x811c9dc5
    for c in name:
        h = (h * 0x01000193) % 0x100000000
        h = (h ^ ord(c.lower())) % 0x100000000
    return h


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


class BIN(SectionNoId):
    """
    英雄联盟BIN文件解析器，用于提取语音触发事件和音乐数据

    解析流程:
    1. 验证文件头(PROP)
    2. 确定文件类型(皮肤文件 or 地图/公共资源文件)
    3. 搜索并处理BANK_UNITS和关联的MUSIC结构
    """
    __slots__ = ['data', 'is_skin_file', 'theme_music']

    def _read(self):
        """读取并解析BIN文件内容"""
        # 初始化属性
        self.data = []  # 主要数据结构：音频组列表
        self.is_skin_file = False
        self.theme_music = []  # 主题音乐，通常只有皮肤BIN文件有

        # 1. 验证文件头
        file_header = self._data.customize('<4s')
        if file_header is None or file_header != HEADER_SIGNATURE:
            logger.error('文件类型错误: 无效的文件头')
            return

        # 2. 确定文件类型
        self._data.seek(0, 0)  # 回到文件开始
        skin_audio_pos = self._find_structure(SKIN_AUDIO_PROPERTIES)
        if skin_audio_pos != -1:
            logger.debug("检测到皮肤文件")
            self.is_skin_file = True
            
            # 如果是皮肤文件，查找并处理主题音乐
            self._data.seek(0, 0)
            theme_music_pos = self._find_structure(THEME_MUSIC)
            if theme_music_pos != -1:
                self._process_theme_music()

        # 3. 处理BANK_UNITS结构和相关的MUSIC数据
        self._data.seek(0, 0)  # 回到文件开始
        while True:
            # 查找BANK_UNITS标记
            bank_units_pos = self._data.find_by_signature(BANK_UNITS_SIGNATURE)
            if bank_units_pos == -1:
                break

            # 处理BANK_UNITS
            bank_units = self._process_bank_units()

            # 创建新的音频组
            audio_group = AudioGroup(bank_units=bank_units)

            # 检查是否有关联的MUSIC数据(非皮肤文件才有)
            if not self.is_skin_file:
                # 记录当前位置，以便检查是否是MUSIC标记
                current_pos = self._data.buffer.tell()
                possible_music_mark = self._data.customize('<I')

                if possible_music_mark == MUSIC:
                    logger.debug("找到与BANK_UNITS关联的MUSIC结构")
                    # MUSIC标记之后跳过1字节
                    self._data.skip(1)
                    # 处理MUSIC数据
                    music_data = self._process_music_data()
                    if music_data:
                        audio_group.music = music_data
                else:
                    # 不是MUSIC标记，恢复位置
                    self._data.seek(current_pos, 0)

            # 将音频组添加到列表
            self.data.append(audio_group)

    def _process_theme_music(self):
        """
        处理皮肤BIN文件中的主题音乐结构
        """
        try:
            # 跳过2字节未知数据
            self._data.skip(2)
            
            # 读取数据长度
            section_length = self._data.customize('<I')
            
            # 读取音乐数量
            music_count = self._data.customize('<I')
            
            if music_count is None or music_count <= 0:
                logger.warning("无法读取主题音乐数量或无主题音乐")
                return
            
            logger.debug(f"发现 {music_count} 个主题音乐")
            
            # 读取每个主题音乐
            for i in range(music_count):
                music_name = self._data.string()
                if music_name:
                    logger.debug(f"读取到主题音乐: {music_name}")
                    self.theme_music.append(music_name)
            
        except Exception as e:
            logger.error(f"解析主题音乐时出错: {str(e)}")

    def _find_structure(self, structure_hash: int) -> int:
        """
        查找特定结构哈希的位置

        :param structure_hash: 结构哈希值
        :return: 找到的位置，未找到返回-1
        """
        current_pos = self._data.buffer.tell()
        structure_bytes = structure_hash.to_bytes(4, byteorder='little')

        # 寻找结构标记
        pos = self._data.find(structure_bytes)
        if pos != -1:
            logger.debug(f"在位置 {pos} 找到结构 0x{structure_hash:08X}")
            return pos

        self._data.seek(current_pos, 0)  # 恢复原位置
        return -1

    def _process_bank_units(self) -> List[EventData]:
        """
        处理BANK_UNITS结构

        :return: 解析到的事件数据列表
        """
        # 跳过标记后的操作和读取部分全局信息
        self._data.skip(2)  # 跳过2字节未知数据
        section_length = self._data.customize('<I')
        unit_count = self._data.customize('<I')

        if section_length is None or unit_count is None or unit_count <= 0:
            logger.warning("无法读取BANK_UNITS信息")
            return []

        logger.debug(f"发现 {unit_count} 个BANK_UNIT")

        events = []

        # 顺序解析每个BANK_UNIT
        for i in range(unit_count):
            try:
                # 读取BANK_UNIT标记
                bank_unit_mark = self._data.customize('<I')
                if bank_unit_mark != BANK_UNIT_SIGNATURE:
                    logger.error(f"无效的BANK_UNIT标记: 0x{bank_unit_mark:08X}")
                    break

                # 读取BANK_UNIT数据长度
                unit_length = self._data.customize('<I')
                if unit_length is None:
                    logger.error(f"无法读取第 {i + 1}/{unit_count} 个BANK_UNIT长度")
                    break

                # 读取元素个数
                element_count = self._data.customize('<H')
                if element_count is None:
                    logger.error(f"无法读取第 {i + 1}/{unit_count} 个BANK_UNIT元素个数")
                    break

                logger.debug(f"BANK_UNIT {i + 1} 包含 {element_count} 个元素，长度 {unit_length} 字节")

                # 记录当前单元的结束位置
                start_pos = self._data.buffer.tell()
                end_pos = start_pos + unit_length - 6  # 减去已读取的长度和元素个数

                # 读取各元素
                category = None
                bank_paths = []
                unit_events = []

                # 顺序读取每个元素
                for j in range(element_count):
                    # 如果超出单元范围，退出循环
                    if self._data.buffer.tell() >= end_pos:
                        logger.warning(f"元素 {j + 1}/{element_count} 超出BANK_UNIT范围")
                        break

                    # 读取元素标记
                    element_mark = self._data.customize('<I')
                    if element_mark is None:
                        logger.warning("无法读取元素标记")
                        break

                    # 处理不同类型的元素
                    if element_mark == NAME_SIGNATURE:
                        # 读取类型
                        type_val = self._data.customize('<B')
                        if type_val != TYPE_STRING:
                            logger.warning(f"NAME元素类型错误: {type_val}")
                            continue

                        # 读取类别名称
                        category = self._data.string()
                        logger.debug(f"读取到类别: {category}")

                    elif element_mark == BANK_PATH_SIGNATURE:
                        # 跳过2字节未知数据
                        self._data.skip(2)

                        # 读取数据长度
                        path_section_length = self._data.customize('<I')

                        # 读取路径数量
                        path_count = self._data.customize('<I')
                        if path_count is None:
                            logger.warning("无法读取银行路径数量")
                            continue

                        # 读取每个路径
                        for _ in range(path_count):
                            path = self._data.string()
                            if path:
                                bank_paths.append(path)

                        logger.debug(f"读取到 {len(bank_paths)} 个银行路径")

                    elif element_mark == EVENTS_SIGNATURE:
                        # 跳过2字节未知数据
                        self._data.skip(2)

                        # 读取数据长度
                        events_section_length = self._data.customize('<I')

                        # 读取事件数量
                        event_count = self._data.customize('<I')
                        if event_count is None:
                            logger.warning("无法读取事件数量")
                            continue

                        # 读取每个事件
                        for _ in range(event_count):
                            event_name = self._data.string()
                            if event_name:
                                unit_events.append(StringHash(event_name, str_fnv_32(event_name)))

                        logger.debug(f"读取到 {len(unit_events)} 个事件")

                    elif element_mark in [VOICE_OVER_SIGNATURE, ASYNCHRONE_SIGNATURE]:
                        # 跳过 类型1字节 数据1字节， 两个是bool类型
                        self._data.skip(2)

                    else:
                        # 未知元素，报错，等待更新处理
                        logger.warning(f"未知元素标记: 0x{element_mark:08X}")
                        raise ValueError(f"未知元素标记: 0x{element_mark:08X}")

                # 确保指针位于BANK_UNIT末尾
                if self._data.buffer.tell() < end_pos:
                    self._data.seek(end_pos, 0)

                # 如果找到类别名称，添加事件数据
                if category:
                    events.append(EventData(
                        category=category,
                        bank_path=bank_paths,
                        events=unit_events
                    ))
                else:
                    # 理论上没这个可能
                    logger.warning(f"BANK_UNIT {i + 1} 没有找到类别名称")

            except Exception as e:
                logger.error(f"解析第 {i + 1}/{unit_count} 个BANK_UNIT时出错: {str(e)}")
                # 异常处理后继续下一个单元
                continue

        return events

    def _process_music_data(self) -> Optional[MusicData]:
        """
        处理音乐数据结构

        :return: 解析到的音乐数据，解析失败返回None
        """
        try:
            # 读取四字节，理论上应该等于MUSIC_AUDIO_DATA_PROPERTIES
            music_audio_data_properties = self._data.customize('<I')
            if music_audio_data_properties != MUSIC_AUDIO_DATA_PROPERTIES:
                logger.error(f"音乐数据结构错误: 0x{music_audio_data_properties:08X}")
                return None

            # 读取数据长度
            section_length = self._data.customize('<I')

            # 读取字段数量
            field_count = self._data.customize('<H')
            if field_count is None:
                logger.warning("无法读取音乐数据字段数量")
                return None

            logger.debug(f"音乐数据包含 {field_count} 个字段")

            # 创建音乐数据对象
            music_data = MusicData()

            # 字段标记到属性名的映射
            field_mapping = {
                THEME_MUSIC_ID: 'theme_music_id',
                THEME_MUSIC_TRANSITION_ID: 'theme_music_transition_id',
                LEGACY_THEME_MUSIC_ID: 'legacy_theme_music_id',
                LEGACY_THEME_MUSIC_TRANSITION_ID: 'legacy_theme_music_transition_id',
                VICTORY_MUSIC_ID: 'victory_music_id',
                DEFEAT_MUSIC_ID: 'defeat_music_id',
                VICTORY_BANNER_SOUND: 'victory_banner_sound',
                DEFEAT_BANNER_SOUND: 'defeat_banner_sound',
                AMBIENT_EVENT: 'ambient_event'
            }

            # 解析每个字段
            for i in range(field_count):
                # 读取字段标记
                field_mark = self._data.customize('<I')
                if field_mark is None:
                    logger.warning("无法读取音乐数据字段标记")
                    break

                # 读取字段类型
                field_type = self._data.customize('<B')
                if field_type is None:
                    logger.warning("无法读取音乐数据字段类型")
                    break

                # 根据字段类型和标记处理数据
                if field_type == TYPE_STRING:
                    value = self._data.string()

                    # 使用映射动态设置属性
                    attr_name = field_mapping.get(field_mark)
                    if attr_name:
                        setattr(music_data, attr_name, value)
                    else:
                        # 保存未知字段
                        logger.warning(f"发现未知音乐数据字段: 0x{field_mark:08X} = {value}")
                        music_data.unknown_fields[field_mark] = value
                else:
                    # 对于非字符串类型，记录并跳过
                    logger.error(f"发现不支持的字段类型: 0x{field_mark:08X}, 类型: {field_type}")

                    raise ValueError(f"发现不支持的字段类型: 0x{field_mark:08X}, 类型: {field_type}")

            logger.debug(f"成功解析音乐数据: {music_data}")
            return music_data

        except Exception as e:
            logger.error(f"解析音乐数据时出错: {str(e)}")
            return None

    def __repr__(self):
        total_units = len(self.data)
        total_events = sum(len(unit.events) for group in self.data for unit in group.bank_units)
        groups_with_music = sum(1 for group in self.data if group.music is not None)
        theme_music_count = len(self.theme_music)

        base_info = (f'Skin_File: {self.is_skin_file}, '
                    f'Audio_Groups: {total_units}, '
                    f'Total_Events: {total_events}, '
                    f'Groups_With_Music: {groups_with_music}')
                    
        if theme_music_count > 0:
            base_info += f', Theme_Music: {theme_music_count}'
            
        return base_info

