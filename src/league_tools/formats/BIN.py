# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 13:14
# @Update  : 2025/4/25 0:07
# @Detail  : 英雄联盟皮肤Bin文件解析(仅提取语音触发事件名称)

import json
from dataclasses import dataclass, field
from typing import List

from loguru import logger

from src.league_tools.base import SectionNoId

# 标记常量定义
HEADER_SIGNATURE = b'PROP'
BANK_UNITS_SIGNATURE = [0x92, 0x9F, 0xF2, 0xF8]  # 银行单元集合标记
BANK_UNIT_SIGNATURE = 0xa4416515  # 银行单元标记
NAME_SIGNATURE = 0x8D39BDE6  # 名称标记
BANK_PATH_SIGNATURE = 0x2A21AD00  # 银行路径标记
EVENTS_SIGNATURE = 0x12D8E384  # 事件标记
VOICE_OVER_SIGNATURE = 0x3B13AA4B  # 语音覆盖标记

# 类型常量
TYPE_STRING = 0x10
TYPE_BOOL = 0x01


def str_fnv_32(name: str) -> int:
    """计算字符串的FNV-1a 32位哈希值"""
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


class BIN(SectionNoId):
    """
    英雄联盟BIN文件解析器，用于提取语音触发事件
    
    解析流程:
    1. 验证文件头(PROP)
    2. 查找银行单元集合标记(BANK_UNITS_SIGNATURE)
    3. 跳过未知数据(2字节)，读取数据长度(4字节)和单元数量(4字节)
    4. 顺序解析每个银行单元:
       a. 验证BANK_UNIT标记(0xa4416515)
       b. 读取数据长度(4字节)和元素个数(2字节)
       c. 读取类别名称(category)
       d. 如果有BANK_PATH标记(0x2A21AD00)，读取银行路径
       e. 如果有EVENTS标记(0x12D8E384)，读取事件列表
       f. 如果有VOICE_OVER标记(0x3B13AA4B)，跳过它
    
    银行路径和事件列表可能为空，但类别名称必须存在
    """
    __slots__ = ['events']

    def _read(self):
        """读取并解析BIN文件内容"""
        self.events = []

        # 1. 验证文件头
        file_header = self._data.customize('<4s')
        if file_header is None or file_header != HEADER_SIGNATURE:
            logger.error('文件类型错误: 无效的文件头')
            return

        # 2. 查找BANK_UNITS标记
        self._data.seek(0, 0)  # 回到文件开始
        bank_units_pos = self._data.find_by_signature(BANK_UNITS_SIGNATURE)
        if bank_units_pos == -1:
            logger.warning("未找到BANK_UNITS标记，跳过此文件")
            return

        # 指针已经位于标记之后，不需要调整

        # 3. 解析BANK_UNITS结构
        # 跳过2字节未知数据
        self._data.skip(2)

        # 读取数据长度
        section_length = self._data.customize('<I')
        if section_length is None:
            logger.error("无法读取BANK_UNITS数据长度")
            return

        # 读取BANK_UNIT数量
        unit_count = self._data.customize('<I')
        if unit_count is None or unit_count <= 0:
            logger.warning("无法读取BANK_UNIT数量或数量为0")
            return

        logger.debug(f"发现 {unit_count} 个BANK_UNIT")

        # 4. 顺序解析每个BANK_UNIT
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
                events = []

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
                                events.append(StringHash(event_name, str_fnv_32(event_name)))

                        logger.debug(f"读取到 {len(events)} 个事件")

                    elif element_mark == VOICE_OVER_SIGNATURE:
                        # 跳过
                        self._data.skip(2)
                        logger.debug("读取到语音覆盖标志")

                    else:
                        # 未知元素，记录并跳过
                        logger.warning(f"未知元素标记: 0x{element_mark:08X}")

                # 确保指针位于BANK_UNIT末尾
                if self._data.buffer.tell() < end_pos:
                    self._data.seek(end_pos, 0)

                # 如果找到类别名称，添加事件数据
                if category:
                    self.events.append(EventData(category=category, bank_path=bank_paths, events=events))

            except Exception as e:
                logger.error(f"解析第 {i + 1}/{unit_count} 个BANK_UNIT时出错: {str(e)}")
                # 异常处理后继续下一个单元
                continue

    def __repr__(self):
        return f'Events_Count: {len(self.events if hasattr(self, "events") else [])}'
