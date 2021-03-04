# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/2 0:57
# @Update  : 2021/3/4 19:38
# @Detail  : 

from ...base import SectionNoId, WemFile


class WPK(SectionNoId):
    __slots__ = [
        'version',
        'file_count',
        'offsets',
        'files'
    ]

    def _read(self):
        head = self._data.customize('4s')
        assert head == b'r3d2', f'WPK文件头错误. {head}'
        self.files = []
        self.version = self._data.customize('<L')
        self.file_count = self._data.customize('<L')
        self.offsets = self._data.customize(f'<{self.file_count}L', False)

        for i in range(self.file_count):
            self._data.seek(self.offsets[i], 0)
            offset, length, filename_size = self._data.customize('<LLL', False)

            # 字符串中间有空字节
            # filename = self._data.str(filename_size * 2)
            filename = bytearray(self._data.customize(f'<{filename_size}H', False)).decode('utf-8')

            self._data.seek(offset, 0)
            data = self._data.bytes(length)

            self.files.append(
                WemFile(
                    filename=filename,
                    data=data,
                    offset=offset,
                    length=length,
                    id=int(filename.split('.')[0])
                )
            )

    def __repr__(self):
        return f'File_Version: {self.version}, ' \
               f'Audio_Resources_Amount: {self.file_count}'