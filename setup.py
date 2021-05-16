# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Pycharm
# @Create  : 2021/3/4 18:48
# @Update  : 2021/5/16 16:11
# @Detail  : 

import setuptools

version = '1.0.0a8'

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lol-voice",
    version=version,
    author="Virace",
    author_email="Virace@aliyun.com",
    description="通过解析英雄联盟游戏内WAD、BNK、WPK、BIN文件来提取语音并可以按照触发事件排序",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Virace/py-bnk-extract",
    project_urls={
        "Bug Tracker": "https://github.com/Virace/py-bnk-extract/issues",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    install_requires=['xxhash', 'zstd'],
    python_requires=">=3.8",

)
