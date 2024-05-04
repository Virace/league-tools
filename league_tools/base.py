# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 19:36
# @Update  : 2024/5/5 7:07
# @Detail  : 块 基类

import os
import subprocess
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Union

from league_tools.tools import BinaryReader


class SectionNoId:
    def __init__(self, data: Union[BinaryReader, BytesIO, bytes, str, os.PathLike]):
        self._data = data
        if not isinstance(data, BinaryReader):
            self._data = BinaryReader(data)

        self._read_object()
        self._read()

    def _read_object(self):
        pass

    def _read(self):
        """
        Rewrite
        :return:
        """
        pass

    def __del__(self):
        del self._data


class Section(SectionNoId):
    __slots__ = [
        'object_id',
        '_data'
    ]

    def __init__(self, data: Union[BinaryReader, BytesIO, bytes, str, os.PathLike]):
        super().__init__(data)

    def _read_object(self):
        self.object_id = self._data.customize('<L')

    def __repr__(self):
        return f'Object_Id: {self.object_id}'

    def __del__(self):
        del self._data


class SectionNoIdBNK(SectionNoId):
    def __init__(self, data: Union[BinaryReader, BytesIO, bytes, str, os.PathLike], version: int = 0):
        self.bnk_version = version
        super().__init__(data)


class SectionBNK(SectionNoIdBNK, Section):
    """
    区别就是加了一个 bnk version
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@dataclass
class WemFile:
    id: int
    offset: int
    length: int
    filename: [str, None] = None
    data: [bytes, None] = None

    def save_file(self, path, wem=True, vgmstream_cli=None):
        """
        保存文件, 如果文件后缀不为wem则自动调用vgmstream转码
        :param path: 文件路径
        :param wem: 如果转码是否保留wem文件
        :param vgmstream_cli: vgmstream_cli程序用来转码
        :return:
        """
        assert self.data, '不存在文件数据, 请调用DATA.get_file后, 在进行保存.'

        self.static_save_file(self.data, path, wem, vgmstream_cli)

    @staticmethod
    def static_save_file(data, path, wem=True, vgmstream_cli=None):
        """
        保存文件静态方法, 如果文件后缀不为wem则自动调用vgmstream转码
        :param data: 数据
        :param path: 文件路径
        :param wem: 如果转码是否保留wem文件
        :param vgmstream_cli: vgmstream_cli程序用来转码
        :return:
        """
        assert data, '不存在文件数据, 请调用DATA.get_file后, 在进行保存.'
        path = Path(path)

        wem_path = path.with_suffix('.wem')

        with open(wem_path, 'wb+') as f:
            f.write(data)

        if (path.suffix != '.wem') and vgmstream_cli:
            subprocess.run([
                vgmstream_cli,
                str(wem_path),
                '-o',
                str(path)
            ],
                stdout=subprocess.DEVNULL,
                timeout=999999999
            )
            if not wem and wem_path.exists():
                wem_path.unlink()
        del data

    def __iter__(self):
        return [self.id, self.offset, self.length]

    def __dict__(self):
        return dict(id=self.id, offset=self.offset, length=self.length)

    def __repr__(self):
        return f'File_Id: {self.id}, ' \
               f'File_Length: {self.length},' \
               f'File_Name: {self.filename}'


