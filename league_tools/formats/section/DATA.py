# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/1 21:09
# @Update  : 2024/5/4 16:50
# @Detail  : Wwise bnk文件, Data块


from typing import List

from league_tools.base import SectionNoIdBNK, WemFile


class DATA(SectionNoIdBNK):
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
        # res = []
        for item in files:
            self._data.seek(item.offset, 0)
            item.data = self._data.bytes(item.length)
            # res.append(
            #     WemFile(
            #         **item.__dict__(),
            #         data=self._data.bytes(item.length)
            #     )
            # )
        return files

    def __repr__(self):
        return f'Data Length: {self._data.end}'

