# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:36
# @Update  : 2022/8/25 21:59
# @Detail  : Wwise bnk文件解析, 目前仅对BKHD、HIRC、DIDX、DATA四种块信息进行处理

from loguru import logger

from lol_voice.base import SectionNoId
from lol_voice.formats.section import DATA, DIDX, HIRC


class BNK(SectionNoId):
    """
    FOR EACH (section) {
        byte[4]: four-letter identifier of the section, e.g. BKHD or DIDX
        uint32: length of this section in bytes
        byte[]: section data (see below)
    } END FOR
    -- END OF FILE --
    """
    head = b'BKHD'
    __slots__ = [
        'objects',
        'section_length',
        'sb_version',
        'sb_id',
        'unknown'
    ]
    parse = {
        # b'BKHD': BKHD,
        b'HIRC': HIRC,
        b'DIDX': DIDX,
        b'DATA': DATA
    }

    def _read(self):
        # 读取文件头
        if self._data.customize('<4s') != self.head:
            raise ValueError('文件类型错误.')

        # 取版本号等信息，详情查看section/BKHD
        self.section_length, self.sb_version, self.sb_id, *self.unknown = self._data.customize('<LLLLL', False)

        self.objects = {}

        # 从头循环
        self._data.seek(0, 0)

        while not self._data.is_end():
            head, length = self._data.customize('<4sL', False)

            _call = self.parse.get(head)
            if _call:
                res = _call(self._data.binary(length), self.sb_version)

                self.objects.update({
                    head: res
                })
            else:
                self._data.seek(length)
                logger.debug(f'Unresolved_object: {head}, '
                             f'Length: {length}')

    def get_data_files(self):
        if b'DATA' not in self.objects:
            # 这说明bnk中没有音频数据, 直接返回
            return []

        return self.objects[b'DIDX'].files

    def __repr__(self):
        return f'SoundBank_Version: {self.sb_version}, ' \
               f'SoundBank_Id: {self.sb_id}, ' \
               f'{self.objects}'
