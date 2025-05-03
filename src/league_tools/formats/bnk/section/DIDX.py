# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/1 21:09
# @Update  : 2025/5/2 18:45
# @Detail  : Wwise bnk文件, DIDX块

from loguru import logger
from src.league_tools.core.section import SectionNoIdBNK, WemFile


class DIDXFormatError(Exception):
    """DIDX区块格式错误"""
    pass


class DIDX(SectionNoIdBNK):
    """
    DIDX (Data Index) 区块包含对SoundBank中嵌入的.wem文件的引用。
    每个音频文件由12字节描述(3个u32)，
    因此可以通过将区块长度除以12来获取嵌入文件的数量。

    44 49 44 58 -- DIDX
    uint32: 区块长度
        FOR EACH (embedded .wem file) {
            uint32: .wem文件ID
            uint32: 从DATA区块开始的偏移量
            uint32: .wem文件的字节长度
        } END FOR
    """
    __slots__ = [
        'files',  # WemFile对象列表
    ]

    def _read(self):
        """
        解析DIDX区块数据
        
        如果区块长度不是12的倍数，将抛出DIDXFormatError异常，
        因为每个文件条目必须正好是12字节(3个u32)。
        """
        total_length = self._data.end
        
        # 验证区块长度是否为12的倍数
        if total_length % 12 != 0:
            error_msg = f"DIDX区块长度 ({total_length}) 不是12的倍数，数据格式可能已改变"
            logger.error(error_msg)
            raise DIDXFormatError(error_msg)
            
        # 计算文件数量并读取每个文件的信息
        file_count = total_length // 12
        logger.debug(f"DIDX区块包含 {file_count} 个文件索引")
        
        self.files = []
        try:
            for i in range(file_count):
                # 读取文件ID、偏移量和长度
                file_id, offset, length = self._data.customize('<LLL', False)
                self.files.append(WemFile(file_id, offset, length))
                logger.trace(f"读取索引 #{i}: ID={file_id}, 偏移={offset}, 长度={length}")
                
        except Exception as e:
            error_msg = f"解析DIDX区块数据时出错: {str(e)}"
            logger.error(error_msg)
            raise DIDXFormatError(error_msg) from e

    def __repr__(self):
        """返回DIDX对象的字符串表示"""
        return f'DIDX: 文件数量={len(self.files)}'


