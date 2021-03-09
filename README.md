# py-bnk-extract

英雄联盟语音解包工具, 由Python语言编写.


- [介绍](#介绍)
- [安装](#安装)
- [使用](#使用)
- [问题](#问题)
- [维护者](#维护者)
- [感谢](#感谢)
- [许可证](#许可证)


### 介绍
可以将英雄联盟中wpk或bnk中音频文件按照皮肤的触发条件分类解包, 默认为wem音频格式, 使用 [vgmstream](https://vgmstream.org/downloads) 可转码.

- [index.py](lol_voice/index.py#L136)中 _extract_audio_ 函数逻辑以及HIRC部分块结构和WPK文件结构参考[Morilli](https://github.com/Morilli)编写的解包工具[https://github.com/Morilli/bnk-extract](https://github.com/Morilli/bnk-extract)
- [WAD.py](lol_voice/formats/WAD.py)中 文件结构以及部分逻辑来源于[https://github.com/CommunityDragon/CDTB](https://github.com/CommunityDragon/CDTB) 和 [https://github.com/Pupix/lol-file-parser](https://github.com/Pupix/lol-file-parser)

其余bnk文件结构来参考:[http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)](http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk))


### 安装



`pip install -e git+https://github.com/Virace/py-bnk-extract@package#egg=lol_voice`

### 使用
此包适合提取已知皮肤语音, 如需全部提取请关注 [lol_extract_voice](https://github.com/Virace/lol_extract_voice)
```
from lol_voice import extract_audio
from lol_voice.formats import WAD


def example():
    """
    按触发事件文件夹分类提取 剑魔 语音文件
    :return:
    """

    # 临时目录和最终输出目录
    temp_path = r'D:\Temp'
    out_path = r'D:\Out'

    # 英雄名字, 以及对于默认皮肤的三个文件路径
    champion = 'aatrox'
    bin_tpl = f'data/characters/{champion}/skins/skin0.bin'
    audio_tpl = f'assets/sounds/wwise2016/vo/zh_cn/characters/aatrox/skins/base/{champion}_base_vo_audio.wpk'
    event_tpl = f'assets/sounds/wwise2016/vo/zh_cn/characters/aatrox/skins/base/{champion}_base_vo_events.bnk'

    # 需要解析两个WAD文件, 这个路径修改为自己的游戏目录
    wad_file1 = r"D:\League of Legends\Game\DATA\FINAL\Champions\Aatrox.wad.client"
    wad_file2 = r"D:\League of Legends\Game\DATA\FINAL\Champions\Aatrox.zh_CN.wad.client"

    # 将上面三个文件提取到临时目录
    WAD(wad_file1).extract([bin_tpl], temp_path)
    WAD(wad_file2).extract([audio_tpl, event_tpl], temp_path)

    # 根据三个文件对应提取语音并整理
    extract_audio(
        bin_file=os.path.join(temp_path, os.path.normpath(bin_tpl)),
        event_file=os.path.join(temp_path, os.path.normpath(event_tpl)),
        audio_file=os.path.join(temp_path, os.path.normpath(audio_tpl)),
        out_dir=out_path
    )

if __name__ == '__main__':
    example()
```
### 问题
待解决：
 - 不同事件调用相同语音, 导致文件重复
 - 不排除文件有缺失问题, event文件解析不完整



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