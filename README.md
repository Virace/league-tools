# league-tools

WAD、BIN、BNK、WPK文件简单处理

- [介绍](#介绍)
- [安装](#安装)
- [使用](#使用)
  - [解析 WPK 文件](#解析-wpk-文件)
  - [解析 BNK 文件](#解析-bnk-文件)
  - [解析 WAD 文件](#解析-wad-文件)
  - [解析 BIN 文件](#解析-bin-文件)
- [参考](#参考)
- [维护者](#维护者)
- [感谢](#感谢)
- [许可证](#许可证)

### 介绍
一个用于处理英雄联盟（League of Legends）数据文件的 Python 库，提供对 `WAD`、`BIN`、`BNK` 和 `WPK` 格式文件的底层解析功能。

- WAD (`.wad.client`): 游戏资源包，包含游戏中的模型、贴图、音频等各种资源。
- BIN (`.bin`): 游戏内的数据文件，用于定义英雄、皮肤、技能等的属性和逻辑。
- BNK (`.bnk`): Wwise SoundBank 格式，包含音频元数据和事件信息。
- WPK (`.wpk`): Wwise Packed File，通常用于打包多个 `.wem` 音频文件。

本库专注于提供稳定、独立的解析器，方便开发者进行二次开发。

### 安装

`pip install league-tools`

`pip install -e git+https://github.com/Virace/py-bnk-extract@package#egg=league_tools`

### 使用

以下是如何使用本库解析四种核心文件格式的示例。

#### 解析 WPK 文件

`WPK` 文件是一个音频包，通常包含多个 `.wem` 文件。

```python
from pathlib import Path
from league_tools.formats.wpk.parser import WPK

# 初始化WPK解析器
wpk_file = WPK('path/to/your/audio.wpk')

# 提取所有包含完整数据的音频文件
# extract_files() 返回一个 WemFile 对象的列表
wem_files = wpk_file.extract_files()

# 创建输出目录
output_dir = Path('./wpk_output')
output_dir.mkdir(exist_ok=True)

# 遍历并保存文件
for wem in wem_files:
    # WemFile.id 是从文件名解析出的数字ID
    # WemFile.data 包含了文件的二进制数据
    print(f"提取文件: ID={wem.id}, 大小={wem.length}字节")
    
    # 定义输出路径
    output_path = output_dir / f"{wem.id}.wem"
    
    # WemFile对象提供了save_file方法，可以直接保存
    if wem.data:
        try:
            wem.save_file(output_path)
        except Exception as e:
            print(f"保存文件 {wem.id}.wem 失败: {e}")
```

#### 解析 BNK 文件

`BNK` 文件是 Wwise SoundBank，它包含音频文件的索引（DIDX）和数据（DATA）。本库的 `BNK` 解析器会自动处理这两部分，并提供统一的接口。

```python
from pathlib import Path
from league_tools.formats.bnk.parser import BNK

# 初始化BNK解析器
bnk_file = BNK('path/to/your/audio.bnk')

# 检查BNK文件版本是否受支持
if not bnk_file.is_version_supported():
    print(f"警告: 不支持的BNK版本 {bnk_file.get_soundbank_version()}")

# 提取所有音频文件
# 如果BNK文件包含DATA区块，返回的WemFile对象将包含完整的二进制数据
wem_files = bnk_file.extract_files()

# 创建输出目录
output_dir = Path('./bnk_output')
output_dir.mkdir(exist_ok=True)

# 遍历并保存文件
for wem in wem_files:
    print(f"提取文件: ID={wem.id}, 大小={wem.length}字节")
    
    # 定义输出路径
    output_path = output_dir / f"{wem.id}.wem"
    
    # BNK解析器已经将数据填充到wem.data属性中
    # 可以直接使用 WemFile 内置的保存方法
    if wem.data:
        try:
            wem.save_file(output_path)
        except Exception as e:
            print(f"保存文件 {wem.id}.wem 失败: {e}")
```

#### 解析 WAD 文件

`WAD` 文件是主要的游戏资源存档。你可以根据文件路径来提取其中的文件。

```python
from pathlib import Path
from league_tools.formats.wad.parser import WAD

# 初始化WAD解析器
wad_file = WAD('path/to/your/archive.wad.client')

# 查看WAD文件中的部分文件信息
# WAD.files 是一个 WADSection 对象的列表
print(f"WAD文件包含 {len(wad_file.files)} 个文件。")
for file_entry in wad_file.files[:5]:
    # WADSection.path_hash 是文件的路径哈希
    print(f" - 文件哈希: {file_entry.path_hash:x}, 大小: {file_entry.size}")

# 创建输出目录
output_dir = Path('./wad_output')
output_dir.mkdir(exist_ok=True)

# 提取单个已知路径的文件
# 注意: WAD内部不存储完整路径，需要提供路径来进行哈希匹配
target_file_path = 'assets/sounds/vo/champions/gwen/skin01/vo_gwen_skin01_events.bnk'

# 直接提取到目录
wad_file.extract([target_file_path], out_dir=output_dir)
print(f"尝试提取文件到: {output_dir / Path(target_file_path).name}")
```

#### 解析 BIN 文件

`BIN` 文件通常用于定义游戏对象的属性，例如英雄皮肤的音频事件。

```python
from league_tools.formats.bin.parser import BIN

# 初始化BIN解析器
bin_file = BIN('path/to/your/skin.bin')

# 检查是否为皮肤文件
if not bin_file.is_skin:
    print("这是一个通用的BIN文件，而非皮肤文件。")

# 遍历文件中的音频组 (AudioGroup)
# 每个AudioGroup包含一个或多个BankUnit
for i, audio_group in enumerate(bin_file.data):
    print(f"--- 音频组 #{i + 1} ---")

    # 遍历BankUnit (通常按类别划分，如Attack, Spell, Emote)
    for unit in audio_group.bank_units:
        print(f"  类别: {unit.category}")
        print(f"  关联的Bank文件: {unit.bank_path}")

        # 打印此类别下的所有音频事件
        for event in unit.events:
            # event.string 是事件名称, e.g., "Play_vo_Gwen_Skin01_Attack2D_3"
            # event.hash 是事件名称的FNV-1a 32位哈希
            print(f"    - 事件: {event.string} (哈希: {event.hash:x})")

    # 如果音频组有关联的音乐数据
    if audio_group.music:
        print("  关联音乐数据:")
        print(f"    - 胜利音乐: {audio_group.music.victory_music_id}")
        print(f"    - 失败音乐: {audio_group.music.defeat_music_id}")
```

### 参考
感谢前人栽树
- WPK参考 [Morilli](https://github.com/Morilli) 编写的解包工具 [bnk-extract](https://github.com/Morilli/bnk-extract)。
- WAD 文件结构及部分逻辑来源于 [CommunityDragon/CDTB](https://github.com/CommunityDragon/CDTB) 和 [Pupix/lol-file-parser](https://github.com/Pupix/lol-file-parser)。
- BNK 文件结构参考自 [Xentax Wiki](http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk))。

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