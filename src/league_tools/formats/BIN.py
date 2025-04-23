# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 13:14
# @Update  : 2023/6/14 20:15
# @Detail  : 英雄联盟皮肤Bin文件解析(仅提取语音触发事件名称)

import json
from dataclasses import dataclass
from typing import List, Union, Optional
from loguru import logger

from src.league_tools.base import SectionNoId


# 常量定义
HEADER_SIGNATURE = b'PROP'
EVENTS_SIGNATURE = [0x15, 0x65, 0x41, 0xA4]
BANK_PATH_MAGIC = 0x2A21AD00
EVENTS_MAGIC = 0x12D8E384


def str_fnv_32(name: str) -> int:
    """
    计算字符串的FNV-1a 32位哈希值
    
    :param name: 输入字符串
    :return: 32位哈希值
    """
    h = 0x811c9dc5

    for c in name:
        h = (h * 0x01000193) % 0x100000000
        h = (h ^ ord(c.lower())) % 0x100000000

    return h


@dataclass
class StringHash:
    """
    字符串哈希数据类，用于存储事件名称及其哈希值
    """
    string: str
    hash: int
    container_id: int = 0  # 容器ID，用于其他模块
    switch_id: int = 0     # 切换ID，用于其他模块
    sound_index: int = 0   # 声音索引，用于其他模块

    @staticmethod
    def dump_cls():
        """
        返回用于JSON序列化的编码器类
        """
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
    """
    事件数据类，存储事件类别、银行路径和事件列表
    """
    category: str
    bank_path: List[str]
    events: List[StringHash]
    
    def __repr__(self):
        return (f'Category: {self.category}, '
                f'Bank_Paths: {len(self.bank_path)}, '
                f'Events: {len(self.events)}')


class BIN(SectionNoId):
    """
    英雄联盟BIN文件解析器，用于提取语音触发事件
    
    文件解析流程:
    1. 验证文件头(PROP) - 确认文件格式正确
    2. 查找特征码[0x15, 0x65, 0x41, 0xA4] - 定位事件数据区域
    3. 读取事件条目数量 - 位于特征码前4字节
    4. 解析每个事件条目:
       a. 跳过15字节 → 读取事件类别(category)
       b. 验证bank路径魔数(0x2A21AD00)
       c. 跳过6字节 → 读取bank路径数量 → 读取每个路径
       d. 验证events魔数(0x12D8E384)
       e. 跳过6字节 → 读取事件数量 → 读取每个事件名称并计算哈希
    
    文件格式说明:
    - 文件头: b'PROP'
    - 事件特征码: [0x15, 0x65, 0x41, 0xA4]
    - 银行路径标记: 0x2A21AD00
    - 事件标记: 0x12D8E384
    """
    __slots__ = ['events']

    def _read(self):
        """
        读取并解析BIN文件内容
        
        :raises ValueError: 当文件格式不正确时抛出
        """
        # 步骤1: 验证文件头
        file_header = self._data.customize('<4s')
        if file_header is None or file_header != HEADER_SIGNATURE:
            raise ValueError('文件类型错误: 无效的文件头.')
        
        # 步骤2: 查找事件数据特征码
        target = self._data.find_by_signature(EVENTS_SIGNATURE)
        if target == -1:
            logger.warning("未找到事件特征码")
            self.events = []
            return
            
        # 步骤3: 解析事件数据
        self.events = self._parse_events(target)
    
    def _parse_events(self, target_pos: int) -> List[EventData]:
        """解析所有事件数据"""
        events_data = []
        
        try:
            # 步骤3.1: 读取条目数量
            self._data.seek(target_pos-4, 0)
            entry_count = self._data.customize('<L')
            
            if entry_count is None:
                logger.error("无法读取事件条目数量")
                return []
                
            logger.debug(f"发现 {entry_count} 个事件条目")
            
            # 步骤3.2: 解析每个条目
            for i in range(entry_count):
                try:
                    # 步骤4: 解析单个事件条目
                    hash_tables = []
                    bank_paths = []
                    
                    # 步骤4.a: 读取类别
                    self._data.seek(15, 1)  # 跳过15个字节
                    category = self._data.string()
                    
                    # 步骤4.b: 验证bank路径标记
                    magic = self._data.customize('<I')
                    if magic is None:
                        raise ValueError("无法读取bank路径标记")
                    if magic != BANK_PATH_MAGIC:
                        raise ValueError(f'bankPath标记错误: 预期 {hex(BANK_PATH_MAGIC)}, 实际 {hex(magic) if magic is not None else "None"}')
                    
                    # 步骤4.c: 读取bank路径
                    self._data.skip(6)  # 跳过6字节
                    bank_count = self._data.customize('<L')
                    if bank_count is None:
                        raise ValueError("无法读取bank路径数量")
                        
                    for _ in range(bank_count):
                        bank_path = self._data.string()
                        bank_paths.append(bank_path)
                    
                    # 步骤4.d: 验证events标记
                    magic = self._data.customize('<I')
                    if magic is None:
                        raise ValueError("无法读取events标记")
                    if magic != EVENTS_MAGIC:
                        raise ValueError(f'events标记错误: 预期 {hex(EVENTS_MAGIC)}, 实际 {hex(magic) if magic is not None else "None"}')
                    
                    # 步骤4.e: 读取事件
                    self._data.seek(6, 1)  # 跳过6字节
                    event_count = self._data.customize('<L')
                    if event_count is None:
                        raise ValueError("无法读取事件数量")
                        
                    for _ in range(event_count):
                        event_name = self._data.string()
                        hash_tables.append(StringHash(event_name, str_fnv_32(event_name)))
                    
                    events_data.append(EventData(category, bank_paths, hash_tables))
                except ValueError as e:
                    logger.error(f"解析第 {i+1} 个事件条目时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"解析事件数据时出错: {str(e)}")
            
        return events_data

    def __repr__(self):
        return f'Events_Count: {len(self.events if hasattr(self, "events") else [])}'


