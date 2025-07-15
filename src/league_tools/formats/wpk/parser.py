# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/3/2 0:57
# @Update  : 2025/5/4 4:10
# @Detail  : WPK文件解析器，处理League of Legends中的WPK音频资源包

from typing import List, Optional
from loguru import logger

from src.league_tools.core.section import SectionNoId, WemFile


class WPKError(Exception):
    """WPK文件解析错误的基类"""
    pass


class WPKHeaderError(WPKError):
    """WPK文件头错误，表示不是一个有效的WPK文件"""
    pass


class WPKFormatError(WPKError):
    """WPK文件格式错误，在正确的文件头下解析失败"""
    pass


class WPK(SectionNoId):
    """
    WPK文件解析器
    
    WPK是League of Legends使用的音频资源封装格式，包含多个WEM音频文件。
    文件结构:
    - 文件头: 'r3d2' 标识
    - 版本号: uint32
    - 文件数量: uint32
    - 文件偏移表: 每个文件的偏移量 (uint32 * 文件数量)
    - 文件数据: 包含偏移量、长度、文件名大小和UTF-16编码的文件名
    """
    
    __slots__ = [
        'version',      # WPK文件版本
        'file_count',   # 包含的文件数量
        'offsets',      # 文件偏移表
        'files'         # 解析出的文件列表
    ]

    # 文件头标识
    FILE_HEADER = b'r3d2'

    def _read(self):
        """
        解析WPK文件内容
        
        :raises WPKHeaderError: 当文件头不是r3d2时
        :raises WPKFormatError: 当解析文件格式出错时
        """
        try:
            # 读取并验证文件头
            head = self._data.customize('<4s')
            if head != self.FILE_HEADER:
                error_msg = f'WPK文件头错误: {head.decode("ascii", errors="backslashreplace")} (预期: r3d2)'
                logger.error(error_msg)
                raise WPKHeaderError(error_msg)
                
            # 初始化变量
            self.files = []
            
            # 读取版本和文件数量
            self.version = self._data.customize('<L')
            self.file_count = self._data.customize('<L')
            
            logger.debug(f"WPK文件版本: {self.version}, 文件数量: {self.file_count}")
            
            # 读取所有文件的偏移表
            self.offsets = self._data.customize(f'<{self.file_count}L', False)
            
            # 解析每个文件的信息
            for i in range(self.file_count):
                try:
                    # 跳转到文件信息位置
                    self._data.seek(self.offsets[i], 0)
                    
                    # 读取文件偏移、长度和文件名大小
                    offset, length, filename_size = self._data.customize('<LLL', False)
                    
                    # 读取并解析UTF-16编码的文件名
                    # 注意: WPK中的文件名采用UTF-16LE编码，每个字符占2字节
                    filename = self._data.str(filename_size * 2, 'utf-16le')
                    
                    # 创建文件对象并添加到列表
                    wem_file = WemFile(
                        filename=filename,
                        offset=offset,
                        length=length,
                        id=int(filename.split('.')[0]) if filename.endswith('.wem') else 0
                    )
                    
                    self.files.append(wem_file)
                    logger.trace(f"解析WPK文件 #{i+1}: {filename}, 偏移={offset}, 长度={length}")
                    
                except Exception as e:
                    error_msg = f"解析WPK文件 #{i+1} 时出错: {str(e)}"
                    logger.error(error_msg)
                    # 继续解析其他文件，不中断整个过程
                    logger.warning(f"将跳过此文件并继续解析")
                    
        except WPKHeaderError:
            # 重新抛出文件头错误
            raise
        except Exception as e:
            error_msg = f"解析WPK文件时出错: {str(e)}"
            logger.error(error_msg)
            raise WPKFormatError(error_msg) from e

    def get_files_data(self) -> List[WemFile]:
        """
        读取所有文件的二进制数据
        
        :return: 填充了二进制数据的WemFile对象列表
        :raises WPKFormatError: 当读取文件数据出错时
        """
        try:
            for i, file in enumerate(self.files):
                try:
                    # 跳转到文件数据位置
                    self._data.seek(file.offset, 0)
                    
                    # 读取文件数据
                    file.data = self._data.bytes(file.length)
                    
                    # 验证数据长度
                    if len(file.data) != file.length:
                        logger.warning(f"文件 {file.filename} 数据长度不匹配: 期望 {file.length}, 实际 {len(file.data)}")
                        
                except Exception as e:
                    error_msg = f"读取文件 {file.filename} 数据时出错: {str(e)}"
                    logger.error(error_msg)
                    # 继续读取其他文件，不中断整个过程
                    
            return self.files
            
        except Exception as e:
            error_msg = f"读取WPK文件数据时出错: {str(e)}"
            logger.error(error_msg)
            raise WPKFormatError(error_msg) from e

    def __repr__(self):
        """返回WPK对象的字符串表示"""
        return f'WPK版本: {self.version}, 文件数量: {self.file_count}'

