# 🐍 Readability counts.
# 🐼 可读性很重要！
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2025/2/9 4:24
# @Update  : 2025/7/25 23:31
# @Detail  : 


# -*- coding: utf-8 -*-
# 🐍 Now is better than never.
# 🐼 做优于不做
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:36
# @Update  : 2025/7/25 23:17
# @Detail  : bnk文件解析, audio.bnk


from typing import Any, Dict, List, Optional, Set

from loguru import logger

from league_tools.core.section import SectionNoId, WemFile

from .section import BKHD, DATA, DIDX


class BNKError(Exception):
    """BNK文件解析错误的基类"""

    pass


class BNKHeaderError(BNKError):
    """BNK文件头错误，表示不是一个有效的BNK文件"""

    pass


class BNKFormatError(BNKError):
    """BNK文件格式错误，在正确的文件头下解析失败"""

    pass


class BNKVersionError(BNKError):
    """BNK文件版本不兼容错误"""

    pass


class BNKSectionError(BNKError):
    """BNK区块解析错误"""

    def __init__(self, section_name: str, message: str, *args):
        """
        初始化BNK区块错误

        :param section_name: 出错的区块名称
        :param message: 错误消息
        """
        self.section_name = section_name
        super().__init__(f"区块 {section_name} 解析错误: {message}", *args)


class BNK(SectionNoId):
    """
    Wwise BNK文件解析器

    文件格式概述:
    FOR EACH (section) {
        byte[4]: four-letter identifier of the section, e.g. BKHD or DIDX
        uint32: length of this section in bytes
        byte[]: section data (see below)
    } END FOR
    -- END OF FILE --

    主要区块说明:
    - BKHD: Bank Header - 文件头信息，包含版本、ID、语言等元数据
    - DIDX: Data Index - 内嵌WEM文件的索引
    - DATA: Data - 内嵌WEM文件的实际音频数据

    注意:
    - HIRC区块(音频层次结构和事件数据)已移至wwiser模块处理

    异常处理说明:
    1. BNKHeaderError: 文件头不是BKHD时抛出，表示这不是有效的BNK文件
    2. BNKFormatError: 当文件虽有正确文件头但后续解析失败时抛出
    3. BNKVersionError: 当识别到不支持的文件版本时抛出
    4. BNKSectionError: 针对特定区块解析问题的详细错误信息
    """

    # 文件头标识
    FILE_HEADER = b"BKHD"

    # 当前支持的资源库生成器版本列表
    SUPPORTED_VERSIONS = {
        134,
        145,
    }

    __slots__ = [
        "_sections",  # 存储解析后的所有区块
        "_bkhd_section",  # BKHD区块的直接引用
        "_didx_section",  # DIDX区块的直接引用
        "_data_section",  # DATA区块的直接引用
        "_files",  # 存储WEM文件列表
        "is_compatible",  # 是否与当前解析器兼容
    ]

    # 区块解析器映射（除BKHD外的其他区块）
    SECTION_PARSERS = {b"DIDX": DIDX, b"DATA": DATA}

    def _read(self):
        """
        解析BNK文件内容

        :raises BNKHeaderError: 当文件头不是BKHD时
        :raises BNKFormatError: 当解析文件格式出错时
        :raises BNKVersionError: 当文件版本不兼容时
        :raises BNKSectionError: 当特定区块解析失败时
        """
        # 初始化对象容器和引用
        self._sections: Dict[bytes, Any] = {}
        self._bkhd_section: Optional[BKHD] = None
        self._didx_section: Optional[DIDX] = None
        self._data_section: Optional[DATA] = None
        self._files: List[WemFile] = []
        self.is_compatible = False

        # 1. 首先解析BKHD区块
        try:
            if not self._parse_bkhd_section():
                # BKHD解析失败
                error_msg = "无法解析BKHD区块，文件格式可能不正确"
                logger.error(error_msg)
                raise BNKFormatError(error_msg)

            # 2. 验证版本兼容性
            if not self._verify_version_compatibility():
                # 版本不兼容
                error_msg = f"BNK版本 {self._bkhd_section.bank_version} 不受支持"
                logger.warning(error_msg)
                raise BNKVersionError(error_msg)

            # 3. 如果版本兼容，继续解析其他区块
            self._parse_remaining_sections()

            # 4. 设置内部区块引用并关联数据
            self._setup_and_associate_data()

        except (BNKHeaderError, BNKFormatError, BNKVersionError, BNKSectionError):
            # 重新抛出已经封装好的错误
            raise
        except Exception as e:
            # 封装其他未预期的错误
            error_msg = f"解析BNK文件时发生未知错误: {str(e)}"
            logger.error(error_msg)
            raise BNKFormatError(error_msg) from e

    def _parse_bkhd_section(self) -> bool:
        """
        单独解析BKHD区块

        :return: 是否成功解析BKHD区块
        :raises BNKHeaderError: 当文件头不是BKHD标识时
        :raises BNKFormatError: 当BKHD区块格式不正确时
        """
        # 重置文件指针到文件开始
        self._data.seek(0, 0)

        try:
            # 验证文件头
            file_header = self._data.customize("<4s")
            if file_header != self.FILE_HEADER:
                error_msg = f"无效的BNK文件：文件头 {file_header.decode('ascii', errors='backslashreplace')} 不是有效的BKHD标识"
                logger.error(error_msg)

                # 使用专门的BNKHeaderError，表示这可能不是BNK文件
                raise BNKHeaderError(error_msg)

            # 读取BKHD区块长度
            section_length = self._data.customize("<L")
            logger.debug(f"发现BKHD区块，长度: {section_length} 字节")

            # 读取BKHD数据并解析
            section_data = self._data.binary(section_length)
            self._bkhd_section = BKHD(section_data)
            self._sections[self.FILE_HEADER] = self._bkhd_section

            logger.debug(
                f"成功解析BKHD区块: 版本={self._bkhd_section.bank_version}, "
                f"资源库ID={self._bkhd_section.soundbank_id}"
            )
            return True

        except BNKHeaderError:
            # 重新抛出文件头错误
            raise
        except Exception as e:
            # 如果是其他错误，则文件头已正确识别，但后续解析失败
            error_msg = f"解析BKHD区块时出错: {str(e)}"
            logger.error(error_msg)
            # 使用BNKFormatError，表示这是格式错误
            raise BNKFormatError(error_msg) from e

    def _verify_version_compatibility(self) -> bool:
        """
        验证资源库生成器版本是否被当前解析器支持

        :return: 版本是否兼容
        :raises BNKFormatError: 当无法验证版本时
        :raises BNKVersionError: 当版本不兼容时
        """
        if not self._bkhd_section:
            error_msg = "无法验证BNK版本：未找到或无法解析BKHD区块"
            logger.warning(error_msg)
            raise BNKFormatError(error_msg)

        version = self._bkhd_section.bank_version
        self.is_compatible = version in self.SUPPORTED_VERSIONS

        if self.is_compatible:
            logger.debug(f"BNK版本 {version} 被当前解析器支持")
            return True
        else:
            logger.warning(f"BNK版本 {version} 不在支持列表中")
            return False

    def _parse_remaining_sections(self):
        """
        解析BKHD之后的其他区块

        :raises BNKFormatError: 当解析基本结构出错时
        :raises BNKSectionError: 当特定区块解析失败时
        """
        try:
            # 从当前位置继续读取剩余区块
            while not self._data.is_end():
                # 读取区块标识和长度
                section_id, section_length = self._data.customize("<4sL", False)
                section_id_str = section_id.decode("ascii", errors="backslashreplace")
                logger.debug(f"发现区块: {section_id_str}, 长度: {section_length} 字节")

                # 跳过已经解析过的BKHD区块
                if section_id == self.FILE_HEADER:
                    self._data.seek(section_length)
                    logger.debug("跳过重复的BKHD区块")
                    continue

                # 跳过HIRC区块，由wwiser模块处理
                if section_id == b"HIRC":
                    self._data.seek(section_length)
                    logger.debug("跳过HIRC区块，该区块由wwiser模块处理")
                    continue

                # 获取对应的解析器
                parser_class = self.SECTION_PARSERS.get(section_id)

                if parser_class:
                    # 解析已知区块
                    try:
                        section_data = self._data.binary(section_length)

                        # 创建区块对象并解析
                        section_obj = parser_class(section_data)

                        # 存储解析结果
                        self._sections[section_id] = section_obj

                        logger.debug(f"成功解析区块: {section_id_str}")
                    except Exception as e:
                        # 使用BNKSectionError，包含区块名称信息
                        error_msg = f"解析区块出错: {str(e)}"
                        logger.error(f"区块 {section_id_str} {error_msg}")
                        raise BNKSectionError(section_id_str, error_msg) from e
                else:
                    # 跳过未知区块或未启用解析的区块
                    self._data.seek(section_length)

                    if section_id in [b"DIDX", b"DATA"]:
                        logger.debug(f"跳过已知但未启用解析的区块: {section_id_str}")
                    else:
                        logger.debug(f"跳过未识别区块: {section_id_str}")

        except BNKSectionError:
            # 重新抛出区块错误
            raise
        except Exception as e:
            # 其它错误视为格式错误
            error_msg = f"解析其他区块时出错: {str(e)}"
            logger.error(error_msg)
            raise BNKFormatError(error_msg) from e

    def _setup_and_associate_data(self):
        """设置内部区块引用，并关联DIDX和DATA区块的数据"""
        # 设置直接引用属性
        self._didx_section = self._sections.get(b"DIDX")
        self._data_section = self._sections.get(b"DATA")

        # 关联数据
        if self._didx_section:
            # 即使没有DATA区块，也从DIDX初始化文件列表（仅含元数据）
            self._files = list(self._didx_section.files)

            # 如果存在DATA区块，则填充数据
            if self._data_section:
                logger.debug("开始关联DIDX和DATA区块...")
                self._data_section.get_files(self._files)  # get_files会原地修改列表

    def get_soundbank_id(self) -> Optional[int]:
        """获取音频资源库ID"""
        return self._bkhd_section.soundbank_id if self._bkhd_section else None

    def get_soundbank_version(self) -> Optional[int]:
        """获取资源库生成器版本"""
        return self._bkhd_section.bank_version if self._bkhd_section else None

    def get_language_id(self) -> Optional[int]:
        """获取语言ID"""
        return self._bkhd_section.language_id if self._bkhd_section else None

    def is_version_supported(self) -> bool:
        """检查当前BNK文件版本是否被解析器支持"""
        return self.is_compatible

    def extract_files(self) -> List[WemFile]:
        """
        获取内嵌的音频文件列表

        如果BNK文件包含DATA区块，则返回的WemFile对象将包含完整的二进制数据。
        否则，只包含元数据（ID、偏移、长度）。

        :return: WemFile对象列表
        """
        return self._files

    @classmethod
    def get_supported_versions(cls) -> Set[int]:
        """获取当前解析器支持的所有资源库生成器版本"""
        return cls.SUPPORTED_VERSIONS

    def __repr__(self):
        """返回BNK对象的字符串表示"""
        if not self._bkhd_section:
            return "无效的BNK文件（未找到或无法解析BKHD区块）"

        section_count = len(self._sections)
        parsed_sections = ", ".join(
            [s.decode("ascii", errors="replace") for s in self._sections.keys()]
        )

        compatibility = "兼容" if self.is_compatible else "不兼容"

        return (
            f"资源库ID: {self.get_soundbank_id()}, "
            f"版本: {self.get_soundbank_version()} ({compatibility}), "
            f"语言ID: {self.get_language_id()}, "
            f"已解析区块数: {section_count} ({parsed_sections})"
        )
