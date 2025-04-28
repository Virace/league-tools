# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:36
# @Update  : 2025/4/29 6:53
# @Detail  : Wwise bnk文件解析, 目前仅对BKHD、HIRC、DIDX、DATA四种块信息进行处理

from typing import Dict, List, Optional, Any, Set

from loguru import logger

from src.league_tools.core.section import SectionNoId
from src.league_tools.formats.bnk.section import HIRC
from .section.BKHD import BKHD


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
    - HIRC: Hierarchy - 音频层次结构和事件数据
    - DIDX: Data Index - 内嵌WEM文件的索引
    - DATA: Data - 内嵌WEM文件的实际音频数据
    
    解析流程:
    1. 首先验证文件头并单独解析BKHD区块
    2. 检查BKHD中的版本号是否受支持
    3. 如果版本受支持，继续解析其他区块
    4. 如果版本不受支持，停止解析并标记为不兼容
    """
    # 文件头标识
    FILE_HEADER = b'BKHD'

    # 当前支持的资源库生成器版本列表
    SUPPORTED_VERSIONS = {
        134,
        145,
    }

    __slots__ = [
        'objects',  # 存储解析后的所有区块
        'header',  # BKHD区块的直接引用
        'data_index',  # DIDX区块的直接引用
        'data',  # DATA区块的直接引用
        'hierarchy',  # HIRC区块的直接引用
        'is_compatible'  # 是否与当前解析器兼容
    ]

    # 区块解析器映射（除BKHD外的其他区块）
    SECTION_PARSERS = {
        b'HIRC': HIRC,
        # b'DIDX': DIDX,
        # b'DATA': DATA
    }

    def _read(self):
        """解析BNK文件内容"""
        # 初始化对象容器和引用
        self.objects = {}
        self.header = None
        self.data_index = None
        self.data = None
        self.hierarchy = None
        self.is_compatible = False

        # 1. 首先解析BKHD区块
        if not self._parse_bkhd_section():
            # BKHD解析失败，直接返回
            return

        # 2. 验证版本兼容性
        if not self._verify_version_compatibility():
            # 版本不兼容，停止解析其他区块
            logger.warning(f'BNK版本 {self.header.bank_version} 不受支持，跳过解析其他区块')
            return

        # 3. 如果版本兼容，继续解析其他区块
        self._parse_remaining_sections()

        # 4. 设置直接引用
        self._setup_direct_references()

    def _parse_bkhd_section(self) -> bool:
        """
        单独解析BKHD区块
        
        返回:
            bool: 是否成功解析BKHD区块
        """
        # 重置文件指针到文件开始
        self._data.seek(0, 0)

        # 验证文件头
        file_header = self._data.customize('<4s')
        if file_header != self.FILE_HEADER:
            logger.error(f'无效的BNK文件：文件头 {file_header} 不是有效的BKHD标识')
            return False

        # 读取BKHD区块长度
        section_length = self._data.customize('<L')
        logger.debug(f'发现BKHD区块，长度: {section_length} 字节')

        try:
            # 读取BKHD数据并解析
            section_data = self._data.binary(section_length)
            self.header = BKHD(section_data)
            self.objects[self.FILE_HEADER] = self.header

            logger.debug(f'成功解析BKHD区块: 版本={self.header.bank_version}, '
                         f'资源库ID={self.header.soundbank_id}')
            return True
        except Exception as e:
            logger.error(f'解析BKHD区块时出错: {str(e)}')
            return False

    def _verify_version_compatibility(self) -> bool:
        """
        验证资源库生成器版本是否被当前解析器支持
        
        返回:
            bool: 版本是否兼容
        """
        if not self.header:
            logger.warning('无法验证BNK版本：未找到或无法解析BKHD区块')
            self.is_compatible = False
            return False

        version = self.header.bank_version
        self.is_compatible = version in self.SUPPORTED_VERSIONS

        if self.is_compatible:
            logger.debug(f'BNK版本 {version} 被当前解析器支持')
            return True
        else:
            logger.warning(f'BNK版本 {version} 不在支持列表中，可能无法正确解析')
            return False

    def _parse_remaining_sections(self):
        """解析BKHD之后的其他区块"""
        # 从当前位置继续读取剩余区块
        while not self._data.is_end():
            # 读取区块标识和长度
            section_id, section_length = self._data.customize('<4sL', False)
            logger.debug(f'发现区块: {section_id.decode("ascii", errors="replace")}, '
                         f'长度: {section_length} 字节')

            # 跳过已经解析过的BKHD区块
            if section_id == self.FILE_HEADER:
                self._data.seek(section_length)
                logger.debug('跳过重复的BKHD区块')
                continue

            # 获取对应的解析器
            parser_class = self.SECTION_PARSERS.get(section_id)

            if parser_class:
                # 解析已知区块
                section_data = self._data.binary(section_length)

                # 创建区块对象并解析
                section_obj = parser_class(section_data)

                # 存储解析结果
                self.objects[section_id] = section_obj

                logger.debug(f'成功解析区块: {section_id.decode("ascii", errors="replace")}')
            else:
                # 跳过未知区块或未启用解析的区块
                self._data.seek(section_length)

                if section_id in [b'HIRC', b'DIDX', b'DATA']:
                    logger.debug(f'跳过已知但未启用解析的区块: {section_id.decode("ascii", errors="replace")}')
                else:
                    logger.debug(f'跳过未识别区块: {section_id.decode("ascii", errors="replace")}')

    def _setup_direct_references(self):
        """为已解析的区块创建直接引用，简化访问"""
        # 设置直接引用属性（只引用已解析的区块）
        # BKHD已在前面直接引用，这里只处理其他区块
        if b'DIDX' in self.objects:
            self.data_index = self.objects[b'DIDX']

        if b'DATA' in self.objects:
            self.data = self.objects[b'DATA']

        if b'HIRC' in self.objects:
            self.hierarchy = self.objects[b'HIRC']

    def get_soundbank_id(self) -> Optional[int]:
        """获取音频资源库ID"""
        return self.header.soundbank_id if self.header else None

    def get_soundbank_version(self) -> Optional[int]:
        """获取资源库生成器版本"""
        return self.header.bank_version if self.header else None

    def get_language_id(self) -> Optional[int]:
        """获取语言ID"""
        return self.header.language_id if self.header else None

    def is_version_supported(self) -> bool:
        """检查当前BNK文件版本是否被解析器支持"""
        return self.is_compatible

    def get_data_files(self) -> List[Dict[str, Any]]:
        """获取内嵌的音频文件信息列表"""
        if not self.data_index:
            # BNK文件中没有可用的索引数据
            return []

        return self.data_index.files

    @classmethod
    def get_supported_versions(cls) -> Set[int]:
        """获取当前解析器支持的所有资源库生成器版本"""
        return cls.SUPPORTED_VERSIONS

    def __repr__(self):
        """返回BNK对象的字符串表示"""
        if not self.header:
            return "无效的BNK文件（未找到或无法解析BKHD区块）"

        section_count = len(self.objects)
        parsed_sections = ', '.join([s.decode('ascii', errors='replace') for s in self.objects.keys()])

        compatibility = "兼容" if self.is_compatible else "不兼容"

        return (f'资源库ID: {self.get_soundbank_id()}, '
                f'版本: {self.get_soundbank_version()} ({compatibility}), '
                f'语言ID: {self.get_language_id()}, '
                f'已解析区块数: {section_count} ({parsed_sections})')
