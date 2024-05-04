# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 13:14
# @Update  : 2024/5/4 16:50
# @Detail  : 英雄联盟皮肤Bin文件解析(仅提取语音触发事件名称)

import json
from dataclasses import dataclass
from typing import List, Union

from league_tools.base import SectionNoId

CHINESE_EVENTS = {
    'oncast': '释放时',
    'onhit': '击中时',
    'basicattack': '普通攻击',
}


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

    @staticmethod
    def dump_cls():
        class Encoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, StringHash):
                    return obj.__dict__

                return json.JSONEncoder.default(self, obj)

        return Encoder

    def __eq__(self, other):
        if self.string == other.string and self.hash == other.hash and self.switch_id == other.switch_id:
            return True
        return False

    def __hash__(self):
        return hash(f'{self.string}{self.hash}{self.switch_id}')

    def __repr__(self):
        return f'String: {self.string}, ' \
               f'Hash: {self.hash}, ' \
               f'Switch_Id: {self.switch_id}'


class BIN(SectionNoId):
    head = b'PROP'
    signature = b'\x84\xe3\xd8\x12'
    __slots__ = [
        'hash_tables',
        'audio_files'
    ]

    def _read_old(self):
        if self._data.customize('<4s') != self.head:
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

    def _read(self):
        if self._data.customize('<4s') != self.head:
            raise ValueError('文件类型错误.')
        self.hash_tables = []
        head = 'ASSETS/Sounds/Wwise2016'
        res = set()
        temp = []
        self._data.seek(4, 0)
        while not self._data.is_end():
            if self._data.find(head) != -1:
                group = []
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
                    if item not in temp:
                        group.append(item)
                    else:
                        temp.append(temp)

                if self._data.bytes(4) == self.signature:
                    self._data.seek(6)
                    count = self._data.customize('<L')
                    for i in range(count):
                        length = self._data.customize('<H')
                        item = self._data.str(length)
                        self.hash_tables.append(StringHash(
                            string=item,
                            hash=str_fnv_32(item)
                        ))
                    if group:
                        res.add(tuple(group))
            else:
                break
        self.audio_files = res

    def get_hash_table(self) -> List:
        """
        输出格式为列表
        :return:
        """
        return [item.__dict__ for item in self.hash_tables]

    @staticmethod
    def load_hash_table(data: Union[str, list]) -> List[StringHash]:
        """
        从文件获取或从列表中解析 StringHash
        :param data:
        :return:
        """
        if isinstance(data, str):
            data = json.load(open(data, encoding='utf-8'))
        return [StringHash(item['string'], item['hash'], item['switch_id']) for item in data]

    def _get_audio_files(self, head='ASSETS/Sounds/Wwise2016') -> List:
        """
        获取于音频有关的文件列表

        例如: 查看当前bin文件中都调用了那些语音相关文件
        以最新版本路径为例, 音频文件均以 ASSETS/Sounds/Wwise2016 为开头
        则直接调用get_files('ASSETS/Sounds/Wwise2016')


        :param head: 路径特征
        :return:
        """
        res = set()
        temp = []
        self._data.seek(4, 0)
        while not self._data.is_end():
            if self._data.find(head) != -1:
                group = []
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
                    if item not in temp:
                        group.append(item)
                    else:
                        temp.append(temp)
                if group:
                    res.add(tuple(group))
            else:
                break
        return list(res)

    def __repr__(self):
        return f'Hash_Table_Amount: {len(self.hash_tables)}'

