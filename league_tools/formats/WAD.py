# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/2 22:36
# @Update  : 2024/9/2 6:43
# @Detail  : 文件结构来源于以下两个库

# https://github.com/Pupix/lol-wad-parser/tree/master/lib
# https://github.com/CommunityDragon/CDTB/blob/master/cdragontoolbox/wad.py

import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import AnyStr, Callable, Dict, List, Optional, Union

import xxhash
import zstd
from loguru import logger

from league_tools.base import SectionNoId
from league_tools.tools import BinaryReader
from league_tools.utils.type_hints import StrPath


@dataclass
class WADSection:
    """
    表示 WAD 文件中的单个文件条目。

    :param path_hash: 文件路径的哈希值，用于在 WAD 存档中唯一标识文件。
    :param offset: 文件数据在 WAD 存档中的字节偏移量，表示从文件头开始的位置。
    :param compressed_size: 文件数据的压缩大小，以字节为单位。
    :param size: 文件解压缩后的大小，以字节为单位。
    :param type: 文件类型，指示文件数据的存储或压缩方式。
    :param duplicate: 是否是重复的文件条目。默认为 False。
    :param first_subchunk_index: 如果文件被分割为子块，则表示第一个子块在子块表中的索引。默认为 None。
    :param sha256: 文件的 SHA-256 哈希值的前 8 个字节，用于完整性验证。默认为 None。
    :param subchunk_count: 文件被分割成的子块数量，从类型字段的高 4 位中派生。
    """

    path_hash: int
    offset: int
    compressed_size: int
    size: int
    type: int
    duplicate: bool = False
    first_subchunk_index: Optional[int] = None
    sha256: Optional[int] = None

    def __post_init__(self):
        self.subchunk_count = (self.type & 0xF0) >> 4
        self.type = self.type & 0xF


class WadHeaderAnalyzer(SectionNoId):
    """
    文件头分析
    用来计算文件头大小，只需要4 + 268 + 4 字节
    """
    __slots__ = [
        'version',
        'file_count',
        'header_size'
    ]

    def _read(self):
        # 4
        head, *self.version = self._data.customize("<2sBB", False)

        if head != b'RW':
            raise ValueError(f'错误的文件头: {head}')

        if self.version[0] > 3:
            raise ValueError(f'不支持的WAD文件版本: {self.version}')

        self.header_size = 4

        self.file_count = getattr(self, f'_v{self.version[0]}')()

        if self.version[0] == 1:
            self.header_size += self.file_count * 24
        else:
            self.header_size += self.file_count * 32

    def _v1(self):
        _entry_header_offset, _entry_header_cell_size, file_count = self._data.customize('<HHL', False)
        self.header_size += 8
        return file_count

    def _v2(self):
        ECDSA_length = self._data.customize('<B')
        _ECDSA = self._data.bytes(ECDSA_length)
        _ECDSA_padding = self._data.bytes(83 - ECDSA_length)
        _files_checksum, _entry_header_offset, _entry_header_cell_size, file_count \
            = self._data.customize('<QHHL', False)
        self.header_size += 100
        return file_count

    def _v3(self):
        """
        256 + 12
        :return:
        """
        _ECDSA = self._data.bytes(256)
        _files_checksum, file_count = self._data.customize('<QL', False)
        self.header_size += 268
        return file_count


class WAD(WadHeaderAnalyzer):

    def _read(self):
        super()._read()

        if self.version[0] == 1:
            self.files = [WADSection(*self._data.customize("<QIIII", False)) for _ in range(self.file_count)]
        else:
            self.files = [WADSection(*self._data.customize("<QIIIB?HQ", False)) for _ in range(self.file_count)]

    @staticmethod
    def get_hash(path: str) -> int:
        """
        计算给定路径的哈希值。

        :param path: 文件路径字符串。
        :return: 64位哈希值。
        """
        xx = xxhash.xxh64()
        xx.update(path.lower().encode('utf-8'))
        return xx.intdigest()

    @classmethod
    def _decompress_subchunks(cls, file: WADSection, data: BinaryReader) -> bytes:
        """
        解压缩类型为 4 的文件（包含子块）。

        :param file: 要解压缩的 WADSection 对象。
        :param data: BinaryReader。
        :return: 解压缩后的数据。
        """
        offset = 0
        decompressed_data = bytearray()
        for _ in range(file.subchunk_count):
            # 每个子块的头部包含压缩大小和未压缩大小
            data.skip(offset)
            subchunk_header = data.customize('<II')
            comp_size, uncomp_size = subchunk_header
            offset += 8  # 跳过头部
            subchunk_data = data[offset:offset + comp_size]
            offset += comp_size

            if comp_size == uncomp_size:
                decompressed_data.extend(subchunk_data)
            else:
                decompressed_data.extend(zstd.decompress(subchunk_data))

        return bytes(decompressed_data)

    def extract_by_section(self, file: WADSection, file_path: StrPath, raw: bool = False):
        """
        提取单个文件。

        :param file: 要提取的 WADSection 对象。
        :param file_path: 提取后保存的文件路径。
        :param raw: 是否返回原始数据而不保存到文件。
        :return: 提取的数据（如果 raw 为 True），或者保存的文件路径。
        """
        file_path = Path(file_path)
        self._data.seek(file.offset, 0)
        compressed_data = self._data.bytes(file.compressed_size)
        # https://github.com/Pupix/lol-wad-parser/blob/2de5a9dafb77b7165b568316d5c1b1f8b5e898f2/lib/extract.js#L11
        # https://github.com/CommunityDragon/CDTB/blob/2663610ed10a2f5fdeeadc5860abca275bcd6af6/cdragontoolbox/wad.py#L82
        try:
            if file.type == 0:
                data = compressed_data
            elif file.type == 1:
                data = gzip.decompress(compressed_data)
            elif file.type == 2:
                data_reader = BinaryReader(compressed_data)
                n = data_reader.customize('<L')
                data_reader.skip(4)
                target = data_reader.bytes(4+n).rstrip(b'\0').decode('utf-8')
                logger.debug(f'文件重定向: {target}')
                return None
            elif file.type == 3:
                data = zstd.decompress(compressed_data)
            elif file.type == 4:
                data = self._decompress_subchunks(file, compressed_data)
            else:
                raise ValueError(f"不支持的文件类型: {file.type}")
        except Exception as e:
            logger.error(f"解压缩文件失败: {e}")
            return None

        if raw:
            return data
        else:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f'提取文件: {file_path}')
            with open(file_path, 'wb') as f:
                f.write(data)
            return file_path

    def extract(self, paths: List[StrPath], out_dir: Union[AnyStr, Callable] = '', raw=False) -> List:
        """
        提取指定路径的文件。

        :param paths: 要提取的文件路径列表。
        :param out_dir: 输出目录或生成输出路径的函数。
        :param raw: 是否返回原始数据而不保存到文件。
        :return: 提取结果列表，对应每个输入路径。
        """
        if not out_dir and not raw:
            raise ValueError('out_dir 与 raw 不能同时为空')

        results = []
        for path in paths:
            path_hash = self.get_hash(path)
            matched_file = next((f for f in self.files if f.path_hash == path_hash), None)

            if matched_file:
                if callable(out_dir):
                    file_path = out_dir(path)
                else:
                    file_path = Path(out_dir) / path
                result = self.extract_by_section(matched_file, file_path, raw)
                results.append(result)
            else:
                logger.warning(f"未找到路径: {path}")
                results.append(None)
        return results

    def extract_hash(self, hashtable: Dict[str, str], out_dir: str = '') -> List:
        """
        提供哈希表, 解包文件.
        :param hashtable:  {'hash:10': 'path:str'}
        :param out_dir: 输出文件夹
        :return:
        """

        ret = []
        for file in self.files:
            if (s := str(file.path_hash)) in hashtable:
                path = hashtable[s]
                file_path = Path(out_dir) / Path(path).as_posix()
                self.extract_by_section(file, file_path)
                ret.append(file_path)
        return ret
