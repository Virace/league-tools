# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:36
# @Update  : 2021/3/9 19:34
# @Detail  : Wwise bnk文件解析, 目前仅对BKHD、HIRC、DIDX、DATA四种块信息进行处理

import logging

from lol_voice.base import SectionNoId
from lol_voice.formats.section import BKHD
from lol_voice.formats.section import DATA
from lol_voice.formats.section import DIDX
from lol_voice.formats.section import HIRC

log = logging.getLogger(__name__)


class BNK(SectionNoId):
    """
    FOR EACH (section) {
        byte[4]: four-letter identifier of the section, e.g. BKHD or DIDX
        uint32: length of this section in bytes
        byte[]: section data (see below)
    } END FOR
    -- END OF FILE --
    """
    __slots__ = [
        'objects'
    ]
    parse = {
        b'BKHD': BKHD,
        b'HIRC': HIRC,
        b'DIDX': DIDX,
        b'DATA': DATA
    }

    def _read(self):
        self.objects = {}
        while not self._data.is_end():
            head, length = self._data.customize('4sL', False)

            _call = self.parse.get(head)
            if _call:
                res = _call(self._data.binary(length))

                self.objects.update({
                    head: res
                })
            else:
                self._data.seek(length)
                log.debug(f'Unresolved_object: {head}, '
                          f'Length: {length}')

    def __repr__(self):
        return f'{self.objects}'
