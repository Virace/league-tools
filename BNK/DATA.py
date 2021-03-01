# -*- coding: utf-8 -*-
# @Time    : 2021/3/1 21:09
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Detail  : Wwise bnk文件, Data块

import logging
from typing import Union, List

from base import SectionNoId

from .DIDX import WemFile

log = logging.getLogger(__name__)


class DATA(SectionNoId):
    """
    The DATA section contains the .wem files, not encoded, and immediately following each other.
    It is not recommended to read this section by itself
    but instead to immediately jump to the correct position based on the offset given in the DIDX or HIRC section.

    44 41 54 41 -- DATA
    uint32: length of section
        FOR EACH (embedded .wem file) {
            byte[]: the .wem file with the length as given in the DIDX section, and starting with 52 49 46 46 -- RIFF.
        } END FOR
    """

    def get_files(self, files: List[WemFile]):
        res = []
        for item in files:
            self._data.seek(item.offset, 0)
            res.append(
                WemFile(
                    **item.__dict__(),
                    data=self._data.bytes(item.length)
                )
            )
        return res

    def __repr__(self):
        return f'Data Length: {len(self._data.end)}'
