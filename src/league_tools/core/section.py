# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2021/2/27 19:36
# @Update  : 2025/4/26 3:27
# @Detail  : 块 基类

import abc
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from league_tools.core import BinaryReader
from league_tools.utils.type_hints import DataSource


class SectionBase:
    """
    所有区段的基础类，提供公共功能
    """

    def __init__(self, data: Union[DataSource, BinaryReader]):
        """
        初始化区段对象
        
        :param data: 二进制数据来源，可以是BinaryReader对象、BytesIO、bytes或文件路径
        """
        if not isinstance(data, BinaryReader):
            self._data: BinaryReader = BinaryReader(data)
        else:
            self._data: BinaryReader = data

        try:
            self._initialize()
        except Exception as e:
            self._cleanup()
            raise e

    def _initialize(self):
        """
        初始化处理流程，子类可自定义流程顺序
        """
        self._read_object()
        self._read()

    def _read_object(self):
        """
        读取对象特有属性，子类可重写此方法
        """
        pass

    def _read(self):
        """
        读取区段内容，默认为空实现
        子类应根据需要重写此方法
        """
        pass

    def _cleanup(self):
        """清理资源"""
        if hasattr(self, '_data') and self._data is not None:
            self._data.close()
            self._data = None

    def __del__(self):
        """析构函数，确保资源被释放"""
        self._cleanup()


class SectionNoId(SectionBase):
    """
    无ID的区段基类
    
    该类提供了基本读取功能，但不包含对象ID
    子类需要重写_read方法实现具体的数据读取逻辑
    """
    pass


class Section(SectionBase):
    """
    带有对象ID的区段基类
    
    该类会读取一个32位无符号整数作为对象ID
    子类可重写_read方法实现具体的数据读取逻辑
    """
    __slots__ = ['object_id', '_data']

    def _read_object(self):
        """读取对象ID"""
        self.object_id = self._data.customize('<L')
        if self.object_id is None:
            raise ValueError("无法读取对象ID，文件可能已损坏或格式不正确")

    def __repr__(self):
        return f'Object_Id: {self.object_id}'


class SectionNoIdBNK(SectionNoId):
    """
    BNK文件专用的无ID区段基类
    
    额外包含BNK文件版本信息
    """

    def __init__(self, data: DataSource, version: int = 0):
        """
        初始化BNK区段对象
        
        :param data: 二进制数据来源
        :param version: BNK文件版本
        """
        self.bnk_version = version
        super().__init__(data)


class SectionBNK(SectionBase):
    """
    BNK文件专用的带ID区段基类
    
    结合了Section和SectionNoIdBNK的功能
    """
    __slots__ = ['object_id', 'bnk_version', '_data']

    def __init__(self, data: DataSource, version: int = 0):
        """
        初始化BNK区段对象
        
        :param data: 二进制数据来源
        :param version: BNK文件版本
        """
        self.bnk_version = version
        super().__init__(data)

    def _read_object(self):
        """读取对象ID"""
        self.object_id = self._data.customize('<L')
        if self.object_id is None:
            raise ValueError("无法读取对象ID，文件可能已损坏或格式不正确")

    def __repr__(self):
        return f'BNK_Version: {self.bnk_version}，Object_Id: {self.object_id}'


@dataclass
class WemFile:
    """
    Wem音频文件数据类
    """
    id: int
    offset: int
    length: int
    filename: Optional[str] = None
    data: Optional[bytes] = None

    def save_file(self, path, wem=True, vgmstream_cli=None):
        """
        保存文件, 如果文件后缀不为wem则自动调用vgmstream转码
        
        :param path: 文件路径
        :param wem: 如果转码是否保留wem文件
        :param vgmstream_cli: vgmstream_cli程序用来转码
        :raises ValueError: 当无文件数据时抛出
        """
        if not self.data:
            raise ValueError('不存在文件数据, 请调用DATA.get_file后, 再进行保存.')

        self.static_save_file(self.data, path, wem, vgmstream_cli)

    @staticmethod
    def static_save_file(data, path, wem=True, vgmstream_cli=None):
        """
        保存文件静态方法, 如果文件后缀不为wem则自动调用vgmstream转码
        
        :param data: 数据
        :param path: 文件路径
        :param wem: 如果转码是否保留wem文件
        :param vgmstream_cli: vgmstream_cli程序用来转码
        :raises ValueError: 当无文件数据时抛出
        """
        if not data:
            raise ValueError('不存在文件数据')

        path = Path(path)
        wem_path = path.with_suffix('.wem')

        try:
            with open(wem_path, 'wb+') as f:
                f.write(data)

            if (path.suffix != '.wem') and vgmstream_cli:
                subprocess.run([
                    vgmstream_cli,
                    str(wem_path),
                    '-o',
                    str(path)
                ],
                    stdout=subprocess.DEVNULL,
                    timeout=999999999
                )
                if not wem and wem_path.exists():
                    wem_path.unlink()
        except Exception as e:
            raise IOError(f"保存文件时出错: {str(e)}") from e

    def __iter__(self):
        yield from [self.id, self.offset, self.length]

    def __dict__(self):
        return dict(id=self.id, offset=self.offset, length=self.length)

    def __repr__(self):
        return f'File_Id: {self.id}, ' \
               f'File_Length: {self.length},' \
               f'File_Name: {self.filename}'


# 向后兼容 - 为避免破坏现有代码，提供原有类继承结构
class _OldSectionNoId(SectionBase, abc.ABC):
    """保持与旧代码兼容的抽象基类"""

    @abc.abstractmethod
    def _read(self):
        """读取区段内容，子类必须实现此方法"""
        pass


# 为确保向后兼容，导出原来的类名
# 新代码应使用上面定义的非抽象基类
SectionNoId_Abstract = _OldSectionNoId
