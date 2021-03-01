# -*- coding: utf-8 -*-
# @Time    : 2021/3/1 21:09
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Detail  : Wwise bnk文件, DIDX块


import logging
from base import SectionNoId, WemFile

log = logging.getLogger(__name__)


class DIDX(SectionNoId):
    """
        The DIDX (Data Index) section contains the references to the .wem files embedded in the SoundBank.
        Each sound file is described with 12 bytes,
        so you can get the number of embedded files by dividing the section length by 12.

        44 49 44 58 -- DIDX
        uint32: length of section
            FOR EACH (embedded .wem file) {
                uint32: .wem file id
                uint32: offset from start of DATA section
                uint32: length in bytes of .wem file
            } END FOR
    """
    __slots__ = [
        'files',
    ]

    def _read(self):
        self.files = []
        for i in range(self._data.end // 12):
            self.files.append(
                WemFile(*self._data.customize('<LLL', False))
            )

    def __repr__(self):
        return f'Number_Of_Wem_Files: {len(self.files)}'
