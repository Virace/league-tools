# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/28 4:33
# @Update  : 2025/7/14 22:25
# @Detail  : Wwise bnk文件, BKHD块

from src.league_tools.core.section import SectionNoId


class BKHD(SectionNoId):
    """
    Wwise BNK文件的BKHD(Bank Header)块解析类
    
    数据结构:
    偏移量    类型    字段名           描述/示例
    -------------------------------------------------------
    0x08    u32     dwBankGeneratorVersion = 145 (资源库生成器版本)
    0x0c    sid     dwSoundBankID   = 816662601 (如'ahri_base_vo_events', 音频资源库ID)
    0x10    sid     dwLanguageID    = 3948448560 (语言ID)
    0x14    u32     uAltValues      = 0x10 (对齐值和设备分配标志)
                bit0    uAlignment      = 16 (对齐值)
                bit16   bDeviceAllocated = 0 (设备分配标志)
    0x18    u32     dwProjectID     = 250 (项目ID)
    0x1c    u32     dwSoundBankType = 0x00 [User] (音频资源库类型)
    0x20    gap     abyBankHash     = 0x10 (16字节哈希值)
    
    注意：传入的数据已经不包含dwTag(BKHD)和dwChunkSize，直接从dwBankGeneratorVersion开始
    """
    __slots__ = [
        '_data',
        'bank_version',         # dwBankGeneratorVersion: 资源库生成器版本
        'soundbank_id',         # dwSoundBankID: 音频资源库ID
        'language_id',          # dwLanguageID: 语言ID
        'alt_values',           # uAltValues: 对齐值和设备分配标志
        'project_id',           # dwProjectID: 项目ID
        'soundbank_type',       # dwSoundBankType: 音频资源库类型
        'bank_hash',            # abyBankHash: 资源库哈希值
    ]

    def _read(self):
        """
        读取BKHD块数据
        
        注意：传入的数据已经从偏移量0x08开始，不包含dwTag和dwChunkSize
        """
        # 获取数据总大小用于后续判断
        total_size = self._data.buffer.seek(0, 2)  # 获取数据总长度
        self._data.seek(0, 0)  # 重置到数据开始位置
        
        # 读取基本字段
        self.bank_version = self._data.customize('<L')
        self.soundbank_id = self._data.customize('<L')
        self.language_id = self._data.customize('<L')
        self.alt_values = self._data.customize('<L')
        
        # 读取可选字段(根据数据长度判断)
        remaining = total_size - 16  # 减去已读取的4个uint32字段(4*4=16字节)
        
        # 读取项目ID (如果有足够数据)
        if remaining >= 4:
            self.project_id = self._data.customize('<L')
            remaining -= 4
            
            # 读取音频资源库类型 (如果有足够数据)
            if remaining >= 4:
                self.soundbank_type = self._data.customize('<L')
                remaining -= 4
                
                # 读取哈希值 (如果有足够数据)
                if remaining >= 16:
                    self.bank_hash = self._data.customize('<16s')
                else:
                    self.bank_hash = None
            else:
                self.soundbank_type = None
                self.bank_hash = None
        else:
            self.project_id = None
            self.soundbank_type = None
            self.bank_hash = None

    @property
    def alignment(self):
        """获取对齐值(uAlignment)，位于uAltValues的低16位"""
        if self.alt_values is not None:
            return self.alt_values & 0xFFFF
        return None

    @property
    def device_allocated(self):
        """获取设备分配标志(bDeviceAllocated)，位于uAltValues的第16位"""
        if self.alt_values is not None:
            return (self.alt_values >> 16) & 0x1
        return None

    def __repr__(self):
        """返回BKHD块的字符串表示"""
        base_info = (
            f'版本: {self.bank_version}, '
            f'资源库ID: {self.soundbank_id}, '
            f'语言ID: {self.language_id}, '
            f'对齐值: {self.alignment}'
        )
        
        if self.project_id is not None:
            base_info += f', 项目ID: {self.project_id}'
        
        if self.soundbank_type is not None:
            base_info += f', 资源库类型: {self.soundbank_type}'
        
        if self.bank_hash is not None:
            # 转换二进制哈希值为十六进制字符串
            hash_hex = self.bank_hash.hex() if isinstance(self.bank_hash, bytes) else 'None'
            base_info += f', 哈希值: {hash_hex[:16]}' + ('...' if len(hash_hex) > 16 else '')
            
        return base_info


