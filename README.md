# league-tools

WAD、BIN、BNK、WPK文件简单处理


- [介绍](#介绍)
- [安装](#安装)
- [使用](#使用)
- [问题](#问题)
- [维护者](#维护者)
- [感谢](#感谢)
- [许可证](#许可证)


### 介绍
可以将英雄联盟中wpk或bnk中音频文件~~按照皮肤的触发条件分类解包~~, 默认为wem音频格式, 使用 [vgmstream](https://vgmstream.org/downloads) 可转码.

- [index.py](src/league_tools/index.py)~~中 _extract_audio_ 函数逻辑以及HIRC部分块结构和WPK文件结构参考[Morilli](https://github.com/Morilli)编写的解包工具[https://github.com/Morilli/bnk-extract](https://github.com/Morilli/bnk-extract)~~
- [WAD.py](src/league_tools/formats/wad/parser.py)中 文件结构以及部分逻辑来源于[https://github.com/CommunityDragon/CDTB](https://github.com/CommunityDragon/CDTB) 和 [https://github.com/Pupix/lol-file-parser](https://github.com/Pupix/lol-file-parser)

其余bnk文件结构来参考:[http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)](http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk))


### 安装


`pip install league-tools`

`pip install -e git+https://github.com/Virace/py-bnk-extract@package#egg=league_tools`

### 使用
此包适合提取已知皮肤语音, 如需全部提取请关注 [lol_extract_voice](https://github.com/Virace/lol_extract_voice)

### 重构进展
1. [x] 文件格式解析
2. [ ] 哈希表处理

这个哈希相关处理准备从此包中移除


### 维护者
**Virace**
- blog: [孤独的未知数](https://x-item.com)

### 感谢
- [@Morilli](https://github.com/Morilli/bnk-extract), **bnk-extract**
- [@Pupix](https://github.com/Pupix/lol-file-parser), **lol-file-parser**
- [@CommunityDragon](https://github.com/CommunityDragon/CDTB), **CDTB** 
- [@vgmstream](https://github.com/vgmstream/vgmstream), **vgmstream**

- 以及**JetBrains**提供开发环境支持
  
  <a href="https://www.jetbrains.com/?from=kratos-pe" target="_blank"><img src="https://cdn.jsdelivr.net/gh/virace/kratos-pe@main/jetbrains.svg"></a>

### 许可证

[GPLv3](LICENSE)