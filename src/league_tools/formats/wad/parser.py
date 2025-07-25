# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/2 22:36
# @Update  : 2025/5/4 5:32
# @Detail  : 文件结构来源于以下两个库

# https://github.com/Pupix/lol-wad-parser/tree/master/lib
# https://github.com/CommunityDragon/CDTB/blob/master/cdtb/wad.py

import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import AnyStr, Callable, Dict, List, Optional, Union

import xxhash
import zstd
from loguru import logger

from league_tools.core import BinaryReader
from league_tools.core.section import SectionNoId
from league_tools.utils.type_hints import StrPath


class MalformedSubchunkError(Exception):
    """子块数据无效或解压失败"""

    def __init__(self, message=""):
        super().__init__(message or "无效的子块数据")


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
        self.path = None  # 文件路径，通过哈希表解析

        logger.trace(f"初始化WADSection: hash={self.path_hash}, offset={self.offset}, "
                     f"大小={self.size}(压缩:{self.compressed_size}), 类型={self.type}, "
                     f"子块数={self.subchunk_count}")


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

        logger.debug(f"读取WAD文件头: 标识={head.decode('ascii', errors='backslashreplace')}, 版本={self.version}")

        if head != b'RW':
            error_msg = f'错误的文件头: {head.decode("ascii", errors="backslashreplace")}'
            logger.error(error_msg)
            raise ValueError(error_msg)

        if self.version[0] > 3:
            error_msg = f'不支持的WAD文件版本: {self.version}'
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.header_size = 4

        # 根据版本解析文件头
        logger.debug(f"解析WAD版本{self.version[0]}.{self.version[1]}文件头")
        self.file_count = getattr(self, f'_v{self.version[0]}')()
        logger.debug(f"WAD文件包含 {self.file_count} 个文件条目")

        # 计算头部大小
        if self.version[0] == 1:
            self.header_size += self.file_count * 24
        elif self.version[0] == 3 and self.version[1] > 3:
            # 版本3.3以上使用新的结构
            self.header_size += self.file_count * 32
        else:
            self.header_size += self.file_count * 32

        logger.debug(f"WAD头部总大小: {self.header_size} 字节")

    def _v1(self):
        _entry_header_offset, _entry_header_cell_size, file_count = self._data.customize('<HHL', False)
        self.header_size += 8
        logger.trace(f"解析v1头部: entry_offset={_entry_header_offset}, cell_size={_entry_header_cell_size}")
        return file_count

    def _v2(self):
        ECDSA_length = self._data.customize('<B')
        _ECDSA = self._data.bytes(ECDSA_length)
        _ECDSA_padding = self._data.bytes(83 - ECDSA_length)
        _files_checksum, _entry_header_offset, _entry_header_cell_size, file_count \
            = self._data.customize('<QHHL', False)
        self.header_size += 100
        logger.trace(f"解析v2头部: ECDSA长度={ECDSA_length}, 文件校验和={_files_checksum:x}, "
                     f"entry_offset={_entry_header_offset}, cell_size={_entry_header_cell_size}")
        return file_count

    def _v3(self):
        """
        256 + 12
        :return:
        """
        _ECDSA = self._data.bytes(256)
        _files_checksum, file_count = self._data.customize('<QL', False)
        self.header_size += 268
        logger.trace(f"解析v3头部: 文件校验和={_files_checksum:x}")
        return file_count


class WAD(WadHeaderAnalyzer):

    def _read(self):
        logger.debug("开始解析WAD文件结构")
        super()._read()

        # 根据版本解析文件条目
        if self.version[0] == 1:
            logger.debug(f"使用v1格式解析 {self.file_count} 个文件条目")
            self.files = [WADSection(*self._data.customize("<QIIII", False)) for _ in range(self.file_count)]
        elif self.version[0] == 3 and self.version[1] > 3:
            # 版本3.3以上
            logger.debug(f"使用v3.{self.version[1]}格式(增强格式)解析 {self.file_count} 个文件条目")
            self.files = []
            for i in range(self.file_count):
                path_hash, offset, compressed_size, size, type, subchunk_index_hi, subchunk_index_lo, checksum = self._data.customize(
                    "<QIIIBBHQ", False)
                subchunk_index = subchunk_index_lo + (subchunk_index_hi << 16)
                logger.trace(f"文件条目 #{i + 1}: hash={path_hash:x}, offset={offset}, 子块索引={subchunk_index}")
                self.files.append(
                    WADSection(path_hash, offset, compressed_size, size, type, False, subchunk_index, checksum))
        else:
            logger.debug(f"使用标准格式解析 {self.file_count} 个文件条目")
            self.files = [WADSection(*self._data.customize("<QIIIB?HQ", False)) for _ in range(self.file_count)]

        logger.debug(f"WAD文件解析完成，共 {len(self.files)} 个文件条目")

        # 统计各类型文件数量
        type_counts = {}
        for f in self.files:
            type_counts[f.type] = type_counts.get(f.type, 0) + 1
        logger.debug(f"文件类型统计: {type_counts}")

    @staticmethod
    def get_hash(path: str) -> int:
        """
        计算给定路径的哈希值，使用xxh3_64_intdigest与CDTB保持一致

        :param path: 文件路径字符串。
        :return: 64位哈希值。
        """
        xx = xxhash.xxh64()
        xx.update(path.lower().encode('utf-8'))
        hash_value = xx.intdigest()
        logger.debug(f"计算路径哈希: {path} -> {hash_value:x}")
        return hash_value

    def _decompress_subchunks(self, file: WADSection, data: bytes) -> bytes:
        """
        解压缩类型为 4 的文件（包含子块）。

        :param file: 要解压缩的 WADSection 对象。
        :param data: 压缩的数据。
        :return: 解压缩后的数据。
        :raises MalformedSubchunkError: 当子块数据解压失败时。
        """
        logger.debug(f"开始解压类型4文件，包含 {file.subchunk_count} 个子块，数据大小 {len(data)} 字节")

        # 创建BinaryReader来处理数据
        data_reader = BinaryReader(data)
        offset = 0
        decompressed_data = bytearray()

        for i in range(file.subchunk_count):
            try:
                # 设置位置到正确的偏移量
                data_reader.seek(offset, 0)
                # 读取子块头部: 压缩大小和未压缩大小
                comp_size, uncomp_size = data_reader.customize('<II')
                offset += 8  # 跳过头部

                logger.trace(
                    f"子块 #{i + 1}: 压缩大小={comp_size}字节, 未压缩大小={uncomp_size}字节, 偏移={offset - 8}")

                # 读取子块数据
                data_reader.seek(offset, 0)
                subchunk_data = data_reader.bytes(comp_size)
                if len(subchunk_data) < comp_size:
                    logger.warning(f"子块 #{i + 1} 数据不足: 需要{comp_size}字节，实际{len(subchunk_data)}字节")

                offset += comp_size

                # 处理子块数据
                if comp_size == uncomp_size:
                    # 数据未压缩
                    logger.trace(f"子块 #{i + 1} 未压缩，直接添加")
                    decompressed_data.extend(subchunk_data)
                else:
                    # 使用zstd解压
                    try:
                        logger.trace(f"子块 #{i + 1} 使用zstd解压")
                        decompressed_chunk = zstd.decompress(subchunk_data)
                        if len(decompressed_chunk) != uncomp_size:
                            logger.warning(
                                f"子块 #{i + 1} 解压后大小不匹配: 期望{uncomp_size}, 实际{len(decompressed_chunk)}")
                        decompressed_data.extend(decompressed_chunk)
                    except Exception as e:
                        error_msg = f"子块 #{i + 1} zstd解压失败: {e}"
                        logger.error(error_msg)
                        raise MalformedSubchunkError(error_msg)

            except Exception as e:
                if not isinstance(e, MalformedSubchunkError):
                    error_msg = f"子块 #{i + 1} 解析失败: {e}"
                    logger.error(error_msg)
                    raise MalformedSubchunkError(error_msg)
                raise

        logger.debug(f"成功解压所有子块，解压后总大小: {len(decompressed_data)} 字节")
        return bytes(decompressed_data)

    def extract_by_section(self, file: WADSection, file_path: StrPath, raw: bool = False, data: bytes = None):
        """
        提取单个文件。

        :param file: 要提取的 WADSection 对象。
        :param file_path: 提取后保存的文件路径。
        :param raw: 是否返回原始数据而不保存到文件。
        :param data: compressed_data
        :return: 提取的数据（如果 raw 为 True），或者保存的文件路径。
        """
        logger.debug(
            f"提取文件: hash={file.path_hash:x}, 类型={file.type}, 大小={file.size}(压缩:{file.compressed_size})")

        if not data:
            logger.trace(f"从偏移 {file.offset} 读取 {file.compressed_size} 字节")
            self._data.seek(file.offset, 0)
            compressed_data = self._data.bytes(file.compressed_size)
        else:
            logger.trace("使用提供的压缩数据")
            compressed_data = data
        # https://github.com/Pupix/lol-wad-parser/blob/2de5a9dafb77b7165b568316d5c1b1f8b5e898f2/lib/extract.js#L11
        # https://github.com/CommunityDragon/CDTB/blob/2663610ed10a2f5fdeeadc5860abca275bcd6af6/cdragontoolbox/wad.py#L82

        try:
            if file.type == 0:
                logger.debug("文件类型0: 无压缩")
                data = compressed_data
            elif file.type == 1:
                logger.debug("文件类型1: gzip压缩")
                data = gzip.decompress(compressed_data)
                logger.trace(f"gzip解压: {file.compressed_size} -> {len(data)} 字节")
            elif file.type == 2:
                logger.debug("文件类型2: 文件重定向")
                data_reader = BinaryReader(compressed_data)
                n = data_reader.customize('<L')
                data_reader.skip(4)
                target = data_reader.bytes(4 + n).rstrip(b'\0').decode('utf-8')
                logger.debug(f'文件重定向: {target}')
                return None
            elif file.type == 3:
                logger.debug("文件类型3: zstd压缩")
                data = zstd.decompress(compressed_data)
                logger.trace(f"zstd解压: {file.compressed_size} -> {len(data)} 字节")
            elif file.type == 4:
                logger.debug(f"文件类型4: 包含 {file.subchunk_count} 个子块的zstd压缩")
                try:
                    data = self._decompress_subchunks(file, compressed_data)
                except MalformedSubchunkError as e:
                    logger.error(f"解压子块失败: {e}")
                    return None
            else:
                error_msg = f"不支持的文件类型: {file.type}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 验证解压后大小
            if data and len(data) != file.size:
                logger.warning(f"解压后数据大小不匹配: 期望{file.size}, 实际{len(data)}")

        except Exception as e:
            logger.error(f"解压缩文件失败: {e}")
            return None

        if raw:
            logger.debug("返回原始数据")
            return data
        else:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f'写入文件: {file_path}')
            with open(file_path, 'wb') as f:
                f.write(data)
            logger.debug(f'文件写入成功: {file_path}')
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
            error_msg = 'out_dir 与 raw 不能同时为空'
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug(f"开始提取 {len(paths)} 个文件")
        results = []
        for i, path in enumerate(paths):
            logger.debug(f"[{i + 1}/{len(paths)}] 提取文件: {path}")
            path_hash = self.get_hash(path)

            matched_file = next((f for f in self.files if f.path_hash == path_hash), None)

            if matched_file:
                logger.debug(f"找到匹配文件: hash={path_hash:x}, 偏移={matched_file.offset}")
                if callable(out_dir):
                    file_path = out_dir(path)
                    logger.trace(f"使用路径生成函数，结果: {file_path}")
                else:
                    file_path = Path(out_dir) / path
                    logger.trace(f"输出路径: {file_path}")
                result = self.extract_by_section(matched_file, file_path, raw)
                results.append(result)
            else:
                logger.warning(f"未找到路径: {path}, hash={path_hash:x}")
                results.append(None)

        logger.debug(f"提取完成: 成功{sum(1 for r in results if r is not None)}/{len(paths)}")
        return results

    def extract_hash(self, hashtable: Dict[str, str], out_dir: str = '') -> List:
        """
        提供哈希表, 解包文件.
        :param hashtable:  {'hash:10': 'path:str'}
        :param out_dir: 输出文件夹
        :return:
        """
        logger.debug(f"使用哈希表提取文件，哈希表大小: {len(hashtable)}, 输出目录: {out_dir}")

        ret = []
        match_count = 0

        for file in self.files:
            hash_str = str(file.path_hash)
            if hash_str in hashtable:
                match_count += 1
                path = hashtable[hash_str]
                logger.debug(f"匹配哈希: {hash_str} -> {path}")
                file_path = Path(out_dir) / Path(path).as_posix()
                result = self.extract_by_section(file, file_path)
                if result:
                    ret.append(file_path)

        logger.debug(f"哈希提取完成: 匹配{match_count}/{len(self.files)}, 成功提取{len(ret)}")
        return ret
