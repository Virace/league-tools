# py-bnk-extract

英雄联盟语音解包工具, 由Python语言编写.


- [介绍](#介绍)
- [安装](#安装)
- [维护者](#维护者)
- [感谢](#感谢)
- [许可证](#许可证)


### 介绍
可以将英雄联盟中wpk或bnk中音频文件按照皮肤的触发条件分类解包, 默认为wem音频格式, 使用 [vgmstream](https://vgmstream.org/downloads) 可转码.

- [index.py](index.py#L136)中 _extract_audio_ 函数逻辑以及HIRC部分块结构和WPK文件结构参考[Morilli](https://github.com/Morilli)编写的解包工具[https://github.com/Morilli/bnk-extract](https://github.com/Morilli/bnk-extract)
- [WAD.py](WAD/WAD.py)中 文件结构以及部分逻辑来源于[https://github.com/CommunityDragon/CDTB](https://github.com/CommunityDragon/CDTB) 和 [https://github.com/Pupix/lol-file-parser](https://github.com/Pupix/lol-file-parser)

其余bnk文件结构来参考:[http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)](http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk))


### 安装

无第三方包, 开发环境Python3.8.


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