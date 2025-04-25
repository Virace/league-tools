# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2025/4/26 3:13
# @Update  : 2025/4/26 3:14
# @Detail  : 


def str_fnv_32(name: str) -> int:
    """
    计算字符串的FNV-1a 32位哈希值

    :param name: 要计算哈希的字符串
    :return: 32位哈希值
    """
    h = 0x811c9dc5
    for c in name:
        h = (h * 0x01000193) % 0x100000000
        h = (h ^ ord(c.lower())) % 0x100000000
    return h