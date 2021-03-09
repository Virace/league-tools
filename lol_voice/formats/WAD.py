# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/2 22:36
# @Update  : 2021/3/9 19:31
# @Detail  : 文件结构来源于以下两个库

# https://github.com/Pupix/lol-wad-parser/tree/master/lib
# https://github.com/CommunityDragon/CDTB/blob/master/cdragontoolbox/wad.py

import gzip
import logging
import os
from dataclasses import dataclass
from typing import List, Dict

import xxhash
import zstd

from lol_voice.base import SectionNoId
from lol_voice.tools import BinaryReader

log = logging.getLogger(__name__)


@dataclass
class WADSection:
    """
        pathHash: parser.uint64(),
        offset: parser.uint(),
        compressedFileSize: parser.uint(),
        fileSize: parser.uint(),
        type: parser.ubyte(),
        duplicate: parser.ubyte(),
        unk: parser.ubyte(),
        unk0: parser.ubyte(),
        // First 8 bytes of the fileEntry sha256
        sha256: parser.uint64()
    """

    path_hash: int
    offset: int
    compressed_file_size: int
    file_size: int
    type: int
    duplicate: int = None
    unk: int = None
    unk_0: int = None
    sha_256: int = None


class WAD(SectionNoId):
    __slots__ = [
        'version'
    ]

    def _read(self):
        head, *self.version = self._data.customize("<2sBB", False)

        if head != b'RW':
            raise ValueError(f'错误的文件头: {head}')

        if self.version[0] > 3:
            raise ValueError(f'不支持的WAD文件版本: {self.version}')
        file_count = getattr(self, f'_v{self.version[0]}')()

        if self.version[0] == 1:
            self.files = [WADSection(*self._data.customize("<QIIII", False)) for _ in range(file_count)]
        else:
            self.files = [WADSection(*self._data.customize("<QIIIBBBBQ", False)) for _ in range(file_count)]

    def _v1(self):
        entry_header_offset, entry_header_cell_size, file_count = self._data.customize('<HHL', False)
        return file_count

    def _v2(self):
        ECDSA_length = self._data.customize('<B')
        ECDSA = self._data.bytes(ECDSA_length)
        ECDSA_padding = self._data.bytes(83 - ECDSA_length)
        files_checksum, entry_header_offset, entry_header_cell_size, file_count \
            = self._data.customize('<QHHL', False)
        return file_count

    def _v3(self):
        ECDSA = self._data.bytes(256)
        files_checksum, file_count = self._data.customize('<QL', False)
        return file_count

    @staticmethod
    def get_hash(path: str):
        xx = xxhash.xxh64()
        xx.update(path.encode('utf-8'))
        return int(xx.hexdigest(), 16)

    def _extract(self, file, file_path):
        self._data.seek(file.offset, 0)
        this = self._data.bytes(file.compressed_file_size)
        # https://github.com/Pupix/lol-wad-parser/blob/2de5a9dafb77b7165b568316d5c1b1f8b5e898f2/lib/extract.js#L11
        # https://github.com/CommunityDragon/CDTB/blob/2663610ed10a2f5fdeeadc5860abca275bcd6af6/cdragontoolbox/wad.py#L82
        if file.type == 0:
            data = this
        elif file.type == 1:
            data = gzip.decompress(this)
        elif file.type == 2:
            data = BinaryReader(this)
            n = data.customize('<L')
            data.skip(4)
            re = data.bytes(4 + n).rstrip(b'\0').decode('utf-8')
            log.debug(f'文件重定向: {re}')
            return
        elif file.type == 3:
            data = zstd.decompress(this)
        else:
            raise ValueError(f"不支持的文件类型: {file.type}")

        file_dir = os.path.dirname(file_path)
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)

        log.debug(f'提取文件: {file_path}')
        with open(file_path, 'wb+') as f:
            f.write(data)

    def extract(self, paths: List[str], out_dir) -> List:
        """
        提供需要解包的文件路径, 解包wad文件
        :param paths: 文件路径列表, 例如['assets/characters/aatrox/skins/base/aatrox.skn']
        :param out_dir: 输出文件夹
        :return:
        """
        ret = []
        for path in paths:
            path_hash = self.get_hash(path)
            for file in self.files:
                if path_hash == file.path_hash:
                    file_path = os.path.join(out_dir, os.path.normpath(path))
                    self._extract(file, file_path)
                    ret.append(file_path)
        return ret

    def extract_hash(self, hashtable: Dict[str, str], out_dir) -> List:
        """
        提供哈希表, 解包文件.
        :param hashtable:  {'hash:10': 'path:str'}
        :param out_dir:
        :return:
        """
        ret = []
        for file in self.files:
            if (s := str(file.path_hash)) in hashtable:
                path = hashtable[s]
                file_path = os.path.join(out_dir, os.path.normpath(path))
                self._extract(file, file_path)
                ret.append(file_path)
        return ret
