# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 13:14
# @Update  : 2021/3/6 3:3
# @Detail  : 英雄联盟皮肤Bin文件解析(仅提取语音触发事件名称)


from dataclasses import dataclass
from ...base import SectionNoId


def str_fnv_32(name: str):
    h = 0x811c9dc5

    for c in name:
        h = (h * 0x01000193) % 0x100000000
        h = (h ^ ord(c.lower())) % 0x100000000

    return h


@dataclass
class StringHash:
    string: str
    hash: int
    switch_id: int = 0

    def __repr__(self):
        return f'String: {self.string}, ' \
               f'Hash: {self.hash}, ' \
               f'Switch_Id: {self.switch_id}'


class BIN(SectionNoId):
    head = b'PROP'
    signature = b'\x84\xe3\xd8\x12'
    __slots__ = [
        'hash_tables'
    ]

    def _read(self):
        if self._data.customize('4s') != self.head:
            raise ValueError('文件类型错误.')
        self.hash_tables = []
        while not self._data.is_end():
            if self._data.find(self.signature) != -1:

                self._data.seek(6)
                count = self._data.customize('<L')
                for i in range(count):
                    length = self._data.customize('<H')
                    item = self._data.str(length)
                    self.hash_tables.append(StringHash(
                        string=item,
                        hash=str_fnv_32(item)
                    ))

    def get_hash_table(self):
        return self.hash_tables

    def get_audio_files(self, head='ASSETS/Sounds/Wwise2016'):
        """
        获取于音频有关的文件列表

        例如: 查看当前bin文件中都调用了那些语音相关文件
        以最新版本路径为例, 音频文件均以 ASSETS/Sounds/Wwise2016 为开头
        则直接调用get_files('ASSETS/Sounds/Wwise2016')


        :param head: 路径特征
        :return:
        """
        res = []
        self._data.seek(4, 0)
        while not self._data.is_end():
            if self._data.find(head) != -1:
                #         uint32: 文件数量
                #         FOR EACH (文件数量) {
                #             uint16: 字符串长度
                #             byte[]: 文件路径字符串
                #         } END FOR
                self._data.seek(-6 - len(head), 1)
                item_length = self._data.customize('<L')
                for i in range(item_length):
                    length = self._data.customize('<H')
                    item = self._data.str(length)
                    res.append(item)
            else:
                break
        return res

    def __repr__(self):
        return f'Hash_Table_Amount: {len(self.hash_tables)}'

