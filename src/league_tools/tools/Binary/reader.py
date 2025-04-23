# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2021/3/4 20:43
# @Update  : 2025/4/24 6:00
# @Detail  : 

import io
import os
import struct
from io import BytesIO, IOBase
from typing import Union, Optional, List, Any, BinaryIO, TypeVar, cast

from loguru import logger

# 定义类型变量简化类型标注
T = TypeVar('T')
FilePathOrBuffer = Union[str, os.PathLike, bytes, BytesIO, IOBase]
BinaryData = Union[bytes, bytearray, List[int], str]


class BinaryReader:
    """
    二进制数据读取器，支持对流、文件的二进制操作
    """

    def __init__(self, file: FilePathOrBuffer):
        """
        初始化二进制读取器
        
        :param file: 文件路径、字节数据或文件对象
        """
        if isinstance(file, (str, os.PathLike)):
            self.buffer = io.open(file, 'rb')
        elif isinstance(file, bytes):
            self.buffer = BytesIO(file)
        else:
            self.buffer = cast(BinaryIO, file)

        # 获取文件大小并重置指针
        self.end = self.buffer.seek(0, 2)
        self.buffer.seek(0)
        self._closed = False

    def _unpack(self, fmt: str, one: bool = True) -> Any:
        """
        解包二进制数据
        
        :param fmt: 结构体格式字符串
        :param one: 是否只返回第一个元素
        :return: 解包后的数据
        """
        length = struct.calcsize(fmt)
        before = self.buffer.tell()
        d1 = self.buffer.read(length)

        if length > len(d1):
            return None if one else []

        data = struct.unpack(fmt, d1)
        logger.trace(f'{fmt}: {length}, before: {before}, after: {self.buffer.tell()}')
        return data[0] if one else data

    def bytes(self, length: Optional[int] = None) -> bytes:
        """
        读取指定长度的字节
        
        :param length: 要读取的字节数，None表示读取所有剩余字节
        :return: 读取的字节数据
        """
        return self.buffer.read(length)

    def str(self, length: int, encoding: str = 'utf-8') -> str:
        """
        读取指定长度的字符串
        
        :param length: 要读取的字节数
        :param encoding: 字符编码
        :return: 解码后的字符串
        """
        data = self._unpack(f'{length}s')
        if data is None:
            return ""
        return data.decode(encoding)
    
    def string(self, encoding: str = 'utf-8') -> str:
        """
        读取字符串
        
        :param encoding: 字符编码
        :return: 解码后的字符串
        """
        length = self.customize('<H')
        return self.str(length)

    def customize(self, f: str, one: bool = True) -> Any:
        """
        自定义解包格式
        
        :param f: 结构体格式字符串
        :param one: 是否只返回第一个元素
        :return: 解包后的数据
        """
        return self._unpack(f, one)

    def binary(self, length: Optional[int] = None) -> 'BinaryReader':
        """
        读取指定长度数据并创建新的BinaryReader
        
        :param length: 要读取的字节数，None表示读取所有剩余字节
        :return: 新的BinaryReader实例
        """
        return BinaryReader(BytesIO(self.buffer.read(length)))

    def skip(self, length: int) -> int:
        """
        跳过指定字节数
        
        :param length: 要跳过的字节数
        :return: 跳过后的位置
        """
        self.buffer.read(length)
        return self.buffer.tell()

    def seek(self, offset: int, whence: int = 1) -> int:
        """
        移动文件指针位置
        
        :param offset: 偏移量
        :param whence: 位置参考：0=文件开始，1=当前位置，2=文件末尾
        :return: 移动后的位置
        """
        return self.buffer.seek(offset, whence)

    def find(self, sub: BinaryData, start: bool = False) -> int:
        """
        查找二进制子序列首次出现的位置
        
        :param sub: 要查找的二进制数据
        :param start: 是否从文件开始处查找
        :return: 找到的位置，未找到返回-1
        """
        # 统一转换为bytes
        if isinstance(sub, list):
            sub = bytes(bytearray(sub))
        elif isinstance(sub, bytearray):
            sub = bytes(sub)
        elif isinstance(sub, str):
            sub = bytes(sub.encode('utf-8'))

        # 从文件开始处查找
        if start:
            self.buffer.seek(0, 0)

        current = self.buffer.tell()
        content = self.bytes()

        # 使用内置find方法查找
        point = content.find(sub)

        # 更新指针位置
        if point != -1:
            self.seek(point + len(sub) + current, 0)

        logger.trace(f'current point: {self.buffer.tell()}')
        return point

    def find_by_signature(self, sub: BinaryData, start: bool = False) -> int:
        """
        根据特征码查找位置，支持通配符(0x3F)
        
        :param sub: 特征码，可以是bytearray、list或str
        :param start: 是否从文件开始处查找
        :return: 找到特征码的位置(特征码之后的位置)，未找到返回-1
        """
        # 转换输入格式
        if isinstance(sub, str):
            sub = bytes(sub.encode('utf-8'))
        elif isinstance(sub, list):
            sub = bytes(bytearray(sub))

        # 如果需要从头开始查找
        if start:
            self.buffer.seek(0, 0)

        # 获取当前位置
        current_pos = self.buffer.tell()

        # 读取内容
        content = self.bytes()

        # 找出通配符位置
        wildcard_positions = [i for i, b in enumerate(sub) if b == 0x3F]
        has_wildcards = len(wildcard_positions) > 0

        # 如果没有通配符，可以直接使用内置的find方法
        if not has_wildcards:
            point = content.find(sub)
            if point != -1:
                # 定位到特征码之后的位置
                self.buffer.seek(current_pos + point + len(sub), 0)
                return point + len(sub)
            return -1

        # 有通配符情况下的查找
        length = len(sub)
        for i in range(len(content) - length + 1):
            match = True
            for j in range(length):
                # 通配符位置无需比较
                if j in wildcard_positions:
                    continue
                if content[i + j] != sub[j]:
                    match = False
                    break
            if match:
                # 找到匹配，定位到特征码之后的位置
                position = i + length
                self.buffer.seek(current_pos + position, 0)
                return position

        return -1

    def is_end(self) -> bool:
        """
        检查是否到达文件末尾
        
        :return: 如果到达文件末尾返回True，否则返回False
        """
        return self.buffer.tell() == self.end

    def close(self) -> None:
        """
        关闭文件资源
        """
        if not self._closed and hasattr(self, 'buffer'):
            self.buffer.close()
            self._closed = True

    def __enter__(self) -> 'BinaryReader':
        """
        支持上下文管理器
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        退出上下文管理器时关闭资源
        """
        self.close()

    def __del__(self) -> None:
        """
        析构函数，确保资源被释放
        """
        self.close()
