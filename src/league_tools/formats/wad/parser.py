"""解析 WAD 目录并按条目读取、解压和重建资源。

格式参考：
https://github.com/Pupix/lol-wad-parser/tree/master/lib
https://github.com/CommunityDragon/CDTB/blob/master/cdtb/wad.py
"""

import gzip
import os
import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import AnyStr, Callable, Dict, List, Optional, Union

import xxhash
import zstd
from loguru import logger

from league_tools.core import BinaryReader
from league_tools.core.binary import BinaryWriter
from league_tools.core.section import SectionNoId
from league_tools.formats.wad.builder import (
    TYPE_RAW,
    V34_ENTRY_SIZE,
    V34_HEADER_SIZE,
    WAD_MAGIC,
    WAD_VERSION,
    compress_for_store,
    entry_checksum,
    pack_entry_v34,
)
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
    :param sha256: 条目校验和。历史命名沿用 sha256，实际语义为 xxh3_64(条目存储字节)。
                   默认为 None。
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

        logger.trace(
            f"初始化WADSection: hash={self.path_hash}, offset={self.offset}, "
            f"大小={self.size}(压缩:{self.compressed_size}), 类型={self.type}, "
            f"子块数={self.subchunk_count}"
        )


class WadHeaderAnalyzer(SectionNoId):
    """
    文件头分析
    用来计算文件头大小，只需要4 + 268 + 4 字节
    """

    __slots__ = ["version", "file_count", "header_size"]

    def _read(self):
        # 4
        head, *self.version = self._data.customize("<2sBB", False)

        logger.debug(f"读取WAD文件头: 标识={head.decode('ascii', errors='backslashreplace')}, 版本={self.version}")

        if head != b"RW":
            error_msg = f"错误的文件头: {head.decode('ascii', errors='backslashreplace')}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if self.version[0] > 3:
            error_msg = f"不支持的WAD文件版本: {self.version}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.header_size = 4

        # 根据版本解析文件头
        logger.debug(f"解析WAD版本{self.version[0]}.{self.version[1]}文件头")
        self.file_count = getattr(self, f"_v{self.version[0]}")()
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
        _entry_header_offset, _entry_header_cell_size, file_count = self._data.customize("<HHL", False)
        self.header_size += 8
        logger.trace(f"解析v1头部: entry_offset={_entry_header_offset}, cell_size={_entry_header_cell_size}")
        return file_count

    def _v2(self):
        ECDSA_length = self._data.customize("<B")
        _ECDSA = self._data.bytes(ECDSA_length)
        _ECDSA_padding = self._data.bytes(83 - ECDSA_length)
        _files_checksum, _entry_header_offset, _entry_header_cell_size, file_count = self._data.customize(
            "<QHHL", False
        )
        self.header_size += 100
        logger.trace(
            f"解析v2头部: ECDSA长度={ECDSA_length}, 文件校验和={_files_checksum:x}, "
            f"entry_offset={_entry_header_offset}, cell_size={_entry_header_cell_size}"
        )
        return file_count

    def _v3(self):
        """
        256 + 12
        :return:
        """
        _ECDSA = self._data.bytes(256)
        _files_checksum, file_count = self._data.customize("<QL", False)
        self.header_size += 268
        logger.trace(f"解析v3头部: 文件校验和={_files_checksum:x}")
        return file_count


class WAD(WadHeaderAnalyzer):
    """保存 WAD 目录，允许多个线程并发提取只读条目。

    同一对象的定位和读取受独立锁保护，解压与输出在锁外进行。
    调用方不得在提取期间重建文件、关闭流或修改条目表。
    """

    thread_safe_reads = True

    def _read(self):
        """读取目录并初始化本次打开的读取锁，原位重建时使旧索引失效。"""
        # rebuild 原位替换后会重新初始化对象，旧目录索引不能继续使用。
        self.__dict__.pop("_file_index", None)
        self._read_lock = threading.Lock()
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
                path_hash, offset, compressed_size, size, type, subchunk_index_hi, subchunk_index_lo, checksum = (
                    self._data.customize("<QIIIBBHQ", False)
                )
                subchunk_index = subchunk_index_lo + (subchunk_index_hi << 16)
                logger.trace(f"文件条目 #{i + 1}: hash={path_hash:x}, offset={offset}, 子块索引={subchunk_index}")
                self.files.append(
                    WADSection(path_hash, offset, compressed_size, size, type, False, subchunk_index, checksum)
                )
        else:
            logger.debug(f"使用标准格式解析 {self.file_count} 个文件条目")
            self.files = [WADSection(*self._data.customize("<QIIIB?HQ", False)) for _ in range(self.file_count)]

        logger.debug(f"WAD文件解析完成，共 {len(self.files)} 个文件条目")

        # 统计各类型文件数量
        type_counts = {}
        for f in self.files:
            type_counts[f.type] = type_counts.get(f.type, 0) + 1
        logger.debug(f"文件类型统计: {type_counts}")

    @cached_property
    def _file_index(self) -> Dict[int, WADSection]:
        """在第一次路径提取时建立索引，后续批次复用同一目录。"""
        return {item.path_hash: item for item in self.files}

    @staticmethod
    def get_hash(path: str) -> int:
        """
        计算给定路径的哈希值（小写路径的 xxh64，所有 WAD 版本一致）。

        :param path: 文件路径字符串。
        :return: 64位哈希值。
        """
        hash_value = xxhash.xxh64_intdigest(path.lower().encode("utf-8"))
        logger.debug(f"计算路径哈希: {path} -> {hash_value:x}")
        return hash_value

    @staticmethod
    def get_hash_v34(path: str) -> int:
        """
        同 get_hash，保留用于兼容旧调用。

        :param path: 文件路径字符串。
        :return: 64位哈希值。
        """
        return WAD.get_hash(path)

    def _get_hash_for_path(self, path: str) -> int:
        """
        计算条目路径哈希。
        """
        return self.get_hash(path)

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
                comp_size, uncomp_size = data_reader.customize("<II", False)
                offset += 8  # 跳过头部

                logger.trace(
                    f"子块 #{i + 1}: 压缩大小={comp_size}字节, 未压缩大小={uncomp_size}字节, 偏移={offset - 8}"
                )

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
                                f"子块 #{i + 1} 解压后大小不匹配: 期望{uncomp_size}, 实际{len(decompressed_chunk)}"
                            )
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
        """提取一个条目，读取完成后在锁外解压与写出。

        Args:
            file: 当前目录中的目标条目。
            file_path: 输出文件路径；raw 模式下不使用。
            raw: 是否直接返回解压后的字节。
            data: 可选的已读取压缩字节，省去源文件读取。

        Returns:
            条目字节或输出路径；无法解压或遇到重定向时返回 None。
        """
        logger.debug(
            f"提取文件: hash={file.path_hash:x}, 类型={file.type}, 大小={file.size}(压缩:{file.compressed_size})"
        )

        if not data:
            logger.trace(f"从偏移 {file.offset} 读取 {file.compressed_size} 字节")
            # seek/read 必须是同一临界区；读取结束即释放，避免串行化解压和写盘。
            with self._read_lock:
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
                n = data_reader.customize("<L")
                data_reader.skip(4)
                target = data_reader.bytes(4 + n).rstrip(b"\0").decode("utf-8")
                logger.debug(f"文件重定向: {target}")
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
            logger.debug(f"写入文件: {file_path}")
            with open(file_path, "wb") as f:
                f.write(data)
            logger.debug(f"文件写入成功: {file_path}")
            return file_path

    def extract(self, paths: List[StrPath], out_dir: Union[AnyStr, Callable] = "", raw=False) -> List:
        """复用目录索引，按输入路径顺序返回提取结果。

        Args:
            paths: 待提取的逻辑路径。
            out_dir: 输出目录或生成目标路径的函数。
            raw: 是否返回字节而不写文件。

        Returns:
            与输入逐项对应的结果；未命中或提取失败的项为 None。

        Raises:
            ValueError: 未启用 raw 且没有提供输出位置。
        """
        if not out_dir and not raw:
            error_msg = "out_dir 与 raw 不能同时为空"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug(f"开始提取 {len(paths)} 个文件")
        results = []
        file_index = self._file_index
        for i, path in enumerate(paths):
            logger.debug(f"[{i + 1}/{len(paths)}] 提取文件: {path}")
            path_hash = self._get_hash_for_path(path)
            matched_file = file_index.get(path_hash)

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

    def extract_hash(self, hashtable: Dict[str, str], out_dir: str = "") -> List:
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

    def rebuild(
        self,
        replacements: Dict[Union[str, int], Union[bytes, StrPath]],
        output: Optional[StrPath] = None,
        *,
        strict: bool = True,
    ) -> Path:
        """
        以 v3.4 全量重写 WAD 并替换指定条目。

        未替换条目按存储字节原样搬运(不解压重压)，type/subchunk/checksum 保留，
        仅重算 offset，旧文件中共享数据的条目在新文件中继续共享；
        替换条目沿用原条目的存储方式(原条目未压缩则原样存储，其余按
        .bnk/.wpk 原样、其他 zstd)，重算 size/checksum，subchunk 字段清零。
        输出版本恒为 3.4。

        :param replacements: {WAD内部路径 或 path_hash: bytes 或本地文件路径}
        :param output: 输出路径；None 表示覆盖源文件(仅当 WAD 从文件路径打开时可用)，
                       覆盖源文件后本对象会自动重新打开，可继续使用
        :param strict: True 时任一替换目标未命中抛 KeyError；False 时跳过并告警
        :return: 输出文件路径
        """
        file_index = {item.path_hash: item for item in self.files}

        resolved: Dict[int, tuple] = {}
        missing = []
        for key, data in replacements.items():
            name_hint = ""
            if isinstance(key, str):
                name_hint = key
                path_hash = self.get_hash(key)
            else:
                path_hash = key
            if path_hash not in file_index:
                missing.append(key)
                continue
            if not isinstance(data, bytes):
                data = Path(data).read_bytes()
            resolved[path_hash] = (data, name_hint)

        if missing:
            message = f"替换目标不存在: {missing}"
            if strict:
                raise KeyError(message)
            logger.warning(message)

        src_path = getattr(self._data.buffer, "name", None)
        if output is None:
            if not src_path:
                raise ValueError("WAD 非文件来源, rebuild 必须指定 output")
            output = src_path
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output.with_name(output.name + ".tmp")

        entries = sorted(self.files, key=lambda f: f.path_hash)
        logger.debug(f"开始重写WAD: {len(entries)} 个条目, 替换 {len(resolved)} 个")
        try:
            with BinaryWriter(tmp_path) as writer:
                writer.bytes(WAD_MAGIC)
                writer.customize("<BB", *WAD_VERSION)
                writer.bytes(b"\x00" * 256)
                writer.customize("<Q", 0)
                writer.customize("<L", len(entries))
                writer.bytes(b"\x00" * (V34_ENTRY_SIZE * len(entries)))

                toc = []
                new_dedup: Dict[int, int] = {}  # 新数据 checksum -> 新 offset
                # (旧 offset, 存储大小) -> 新 offset。空条目可能与真实数据共享
                # 同一 offset,仅按 offset 去重会让真实条目指向未写入的数据
                moved: Dict[tuple, int] = {}
                for entry in entries:
                    if entry.path_hash in resolved:
                        data, name_hint = resolved[entry.path_hash]
                        compression = "raw" if entry.type == TYPE_RAW else "auto"
                        stored, entry_type = compress_for_store(data, name_hint, compression)
                        checksum = entry_checksum(stored)
                        offset = new_dedup.get(checksum)
                        if offset is None:
                            offset = writer.tell()
                            writer.bytes(stored)
                            new_dedup[checksum] = offset
                        toc.append(
                            pack_entry_v34(entry.path_hash, offset, len(stored), len(data), entry_type, 0, 0, checksum)
                        )
                    else:
                        moved_key = (entry.offset, entry.compressed_size)
                        offset = moved.get(moved_key)
                        if offset is None:
                            self._data.seek(entry.offset, 0)
                            stored = self._data.bytes(entry.compressed_size)
                            offset = writer.tell()
                            writer.bytes(stored)
                            moved[moved_key] = offset
                        toc.append(
                            pack_entry_v34(
                                entry.path_hash,
                                offset,
                                entry.compressed_size,
                                entry.size,
                                entry.type,
                                entry.subchunk_count,
                                entry.first_subchunk_index or 0,
                                entry.sha256 or 0,
                            )
                        )

                writer.seek(V34_HEADER_SIZE)
                writer.bytes(b"".join(toc))

            overwrite_source = bool(src_path) and output.exists() and os.path.samefile(src_path, output)
            if overwrite_source:
                self._data.close()
            os.replace(tmp_path, output)
            if overwrite_source:
                self.__init__(str(output))
        finally:
            tmp_path.unlink(missing_ok=True)

        logger.debug(f"重写完成: {output}")
        return output
