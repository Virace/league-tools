# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:33
# @Update  : 2024/5/4 16:50
# @Detail  : Wwise bnk文件, BKHD块

from league_tools.base import SectionNoId


class BKHD(SectionNoId):
    """
    https://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)
    The BKHD section (Bank Header) contains the version number and the SoundBank id.

        42 4B 48 44 -- BKHD
        uint32: length of section
        uint32: version number of this SoundBank
        uint32: id of this SoundBank
        uint32: always zero
        uint32: always zero
    """
    __slots__ = [
        '_data',
        'section_length',
        'sb_version',
        'sb_id',
        'unknown',

    ]

    def _read(self):
        self.section_length, self.sb_version, self.sb_id, *self.unknown = self._data.customize('<LLLLL', False)

    def __repr__(self):
        return f'Section_Length: {self.section_length}, ' \
               f'SoundBank_Version: {self.sb_version}, ' \
               f'SoundBank_Id: {self.sb_id}, ' \
               f'Unknown: {self.unknown}'

