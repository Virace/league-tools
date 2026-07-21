# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2026/7/21
# @Update  : 2026/7/21
# @Detail  : WAD v3.4 打包

import os
import struct
from pathlib import Path
from typing import Dict, Tuple, Union

import xxhash
import zstd
from loguru import logger

from league_tools.core.binary import BinaryWriter
from league_tools.utils.type_hints import StrPath

WAD_MAGIC = b'RW'
WAD_VERSION = (3, 4)
V34_HEADER_SIZE = 272
V34_ENTRY_SIZE = 32

TYPE_RAW = 0
TYPE_ZSTD = 3

# Wwise 音频容器自身已压缩，再压无收益，按原样存储
RAW_STORE_SUFFIXES = ('.bnk', '.wpk')


def pack_entry_v34(path_hash: int, offset: int, compressed_size: int, size: int,
                   entry_type: int, subchunk_count: int, subchunk_index: int,
                   checksum: int) -> bytes:
    """
    序列化 v3.4 条目(32 字节)。

    subchunk_index 为 24 位混合端序，磁盘字节序 [hi][lo][mi]；
    v3.4 条目没有 is_duplicate 字节，去重仅表现为共享 offset。
    """
    type_byte = (entry_type & 0xF) | ((subchunk_count & 0xF) << 4)
    index_bytes = bytes((
        (subchunk_index >> 16) & 0xFF,
        subchunk_index & 0xFF,
        (subchunk_index >> 8) & 0xFF,
    ))
    return struct.pack('<QIIIB3sQ', path_hash, offset, compressed_size, size,
                       type_byte, index_bytes, checksum)


def entry_checksum(stored: bytes) -> int:
    """
    条目 checksum：xxh3_64(条目在文件中的存储字节)。
    """
    return xxhash.xxh3_64_intdigest(stored)


def compress_for_store(data: bytes, path_hint: str,
                       compression: str = 'auto') -> Tuple[bytes, int]:
    """
    按存储策略压缩数据，返回 (存储字节, 条目类型)。

    'auto'：path_hint 以 .bnk/.wpk 结尾时原样存储(type 0)，其余 zstd(type 3)；
    'raw' / 'zstd'：显式指定。
    """
    if compression == 'auto':
        compression = 'raw' if path_hint.lower().endswith(RAW_STORE_SUFFIXES) else 'zstd'
    if compression == 'raw':
        return data, TYPE_RAW
    if compression == 'zstd':
        return zstd.compress(data), TYPE_ZSTD
    raise ValueError(f'不支持的压缩方式: {compression}')


class WADBuilder:
    """
    从零打包 v3.4 WAD。

    - TOC 按 path_hash 升序(客户端二分查找依赖)
    - 相同存储内容(checksum 相同)只写一份数据，多条目共享 offset
    - 头部 ECDSA 签名与校验和全零(客户端不校验)
    - 同一路径/哈希重复添加时后写覆盖
    """

    def __init__(self):
        # {path_hash: (bytes 或源文件 Path, compression, path_hint)}
        self._entries: Dict[int, Tuple[Union[bytes, Path], str, str]] = {}

    def add(self, path: str, data: Union[bytes, StrPath], *,
            compression: str = 'auto') -> 'WADBuilder':
        """
        按 WAD 内部路径添加条目。

        :param path: WAD 内部路径，用于计算 xxh64 哈希与压缩策略
        :param data: 文件内容 bytes，或本地文件路径(save 时才读取)
        :param compression: 'auto' | 'raw' | 'zstd'
        """
        path_hash = xxhash.xxh64_intdigest(path.lower().encode('utf-8'))
        return self.add_by_hash(path_hash, data, compression=compression, name_hint=path)

    def add_by_hash(self, path_hash: int, data: Union[bytes, StrPath], *,
                    compression: str = 'auto', name_hint: str = '') -> 'WADBuilder':
        """
        按已知 path_hash 添加条目(明文路径未知的场景)。

        :param path_hash: 条目的 xxh64 路径哈希
        :param data: 文件内容 bytes，或本地文件路径(save 时才读取)
        :param compression: 'auto' | 'raw' | 'zstd'
        :param name_hint: 可选路径提示，仅用于 'auto' 压缩策略判断
        """
        if path_hash in self._entries:
            logger.warning(f'重复条目覆盖: hash={path_hash:016x}')
        if not isinstance(data, bytes):
            data = Path(data)
        self._entries[path_hash] = (data, compression, name_hint)
        return self

    def save(self, output: StrPath) -> Path:
        """
        写入到文件：先写同目录临时文件，成功后原子替换。
        """
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output.with_name(output.name + '.tmp')
        try:
            with BinaryWriter(tmp_path) as writer:
                self._build(writer)
            os.replace(tmp_path, output)
        finally:
            tmp_path.unlink(missing_ok=True)
        logger.debug(f'WAD已写入: {output}')
        return output

    def to_bytes(self) -> bytes:
        """
        打包并返回完整文件字节(内存模式)。
        """
        with BinaryWriter() as writer:
            self._build(writer)
            return writer.getvalue()

    def _build(self, writer: BinaryWriter):
        """
        写头部与 TOC 占位 → 顺序写数据区(去重) → 回填 TOC。
        """
        entries = sorted(self._entries.items())
        count = len(entries)
        logger.debug(f'开始打包WAD v3.4: {count} 个条目')

        writer.bytes(WAD_MAGIC)
        writer.customize('<BB', *WAD_VERSION)
        writer.bytes(b'\x00' * 256)
        writer.customize('<Q', 0)
        writer.customize('<L', count)
        writer.bytes(b'\x00' * (V34_ENTRY_SIZE * count))

        toc = []
        dedup: Dict[int, int] = {}  # checksum -> offset
        for path_hash, (data, compression, name_hint) in entries:
            if not isinstance(data, bytes):
                data = data.read_bytes()
            stored, entry_type = compress_for_store(data, name_hint, compression)
            checksum = entry_checksum(stored)
            offset = dedup.get(checksum)
            if offset is None:
                offset = writer.tell()
                writer.bytes(stored)
                dedup[checksum] = offset
            toc.append(pack_entry_v34(path_hash, offset, len(stored), len(data),
                                      entry_type, 0, 0, checksum))

        writer.seek(V34_HEADER_SIZE)
        writer.bytes(b''.join(toc))
        logger.debug(f'打包完成: 数据段 {len(dedup)} 个, 去重条目 {count - len(dedup)} 个')
