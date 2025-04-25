# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2024/3/12 12:39
# @Update  : 2025/4/26 3:26
# @Detail  : 

import os
from io import BytesIO, IOBase
from typing import Union, List, TypeVar

StrPath = Union[str, 'os.PathLike[str]']

# 定义类型变量简化类型标注
T = TypeVar('T')
DataSource = Union[str, bytes, BytesIO, IOBase, os.PathLike]
BinaryData = Union[bytes, bytearray, List[int], str]
