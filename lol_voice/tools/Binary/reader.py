# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2021/3/4 20:43
# @Update  : 2021/3/6 3:7
# @Detail  : 

# -*- coding:utf-8 -*-
# Author:Virace

import struct
import logging
from typing import *
from io import IOBase, BytesIO
import io

log = logging.getLogger(__name__)


class BinaryReader:
    """
    以二进制操作流、文件
    """

    def __init__(self, file: Union[IOBase, BytesIO, bytes, str]):
        if isinstance(file, str):
            self.buffer = io.open(file, 'rb')
        elif isinstance(file, bytes):
            self.buffer = BytesIO(file)
        else:
            self.buffer = file

        self.end = self.buffer.seek(0, 2)
        self.buffer.seek(0)

    def _unpack(self, fmt, one=True):
        """
        解包
        :param fmt: 表达式
        :param one: 是否仅取第一位
        :return:
        """
        length = struct.calcsize(fmt)
        before = self.buffer.tell()
        data = struct.unpack(fmt, self.buffer.read(length))
        log.debug(f'{fmt}: {length}, before: {before}, after: {self.buffer.tell()}')
        return data[0] if one else data

    def bytes(self, length=None) -> bytes:
        """
        读字节 file.read
        :param length:
        :return:
        """
        return self.buffer.read(length)

    def str(self, length, encoding='utf-8'):
        """
        读字符串(字节集转字符串)
        :param length:
        :param encoding:
        :return:
        """

        data = self._unpack(f'{length}s')

        return data.decode(encoding)

    def customize(self, f, one=True):
        """
        自定义解包
        :param f:
        :param one:
        :return:
        """
        return self._unpack(f, one)

    def binary(self, length=None):
        """
        读取后重新打包为BinaryReader
        :param length:
        :return:
        """
        return BinaryReader(BytesIO(self.buffer.read(length)))

    def skip(self, lenght):
        """
        跳过
        :param lenght:
        :return:
        """
        self.buffer.read(lenght)
        return self.buffer.tell()

    def seek(self, offset: int, whence: int = 1):
        """
        跳转, 默认从当前指针位置跳转
        :param offset: 偏移
        :param whence: 位置
        :return:
        """

        self.buffer.seek(offset, whence)

    def find(self, sub: Union[bytes, bytearray, list, str], start=False):
        """
        查询, 支持字节、字节数组、10进制数组
        :param sub:
        :param start:
        :return: 返回当前指针位置
        """
        if isinstance(sub, list):
            sub = bytes(bytearray(sub))
        elif isinstance(sub, bytearray):
            sub = bytes(sub)
        elif isinstance(sub, str):
            sub = bytes(sub.encode('utf-8'))

        if start:
            self.buffer.seek(0, 0)

        current = self.buffer.tell()

        point = self.bytes().find(sub)

        if point != -1:
            self.seek(point + len(sub) + current, 0)
        log.debug(f'current point3: {self.buffer.tell()}')
        return point

    def is_end(self):
        """
        是否为流结尾
        :return:
        """
        return self.buffer.tell() == self.end

    def __del__(self):
        if getattr(self, 'buffer', None):
            self.buffer.close()

