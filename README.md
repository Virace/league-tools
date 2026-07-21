# league-tools

[![PyPI 版本](https://img.shields.io/pypi/v/league-tools.svg)](https://pypi.org/project/league-tools/)
[![Python 版本](https://img.shields.io/pypi/pyversions/league-tools.svg)](https://pypi.org/project/league-tools/)
[![许可证](https://img.shields.io/pypi/l/league-tools.svg)](LICENSE)
[![发布流程](https://github.com/Virace/league-tools/actions/workflows/python-publish.yml/badge.svg)](https://github.com/Virace/league-tools/actions/workflows/python-publish.yml)

WAD、BIN、BNK、WPK 文件处理工具库。

## 介绍

`league-tools` 是一个用于处理英雄联盟资源文件的 Python 库，提供对以下格式的底层解析能力：

- `WAD`（`.wad.client`）：资源包（模型、贴图、音频等）
- `BIN`（`.bin`）：游戏配置与逻辑数据
- `BNK`（`.bnk`）：Wwise SoundBank 音频元数据
- `WPK`（`.wpk`）：Wwise 打包音频文件

音频事件映射默认推荐使用 `NativeHIRC`：

- 只关注事件映射所需的 HIRC 音频信息
- 直接从 `events.bnk` 读取，速度明显快于 `wwiser -> XML`
- 更适合默认映射链和批量分析

如果你需要更完整的 BNK/HIRC 结构、XML 对照能力或调试信息，再使用 `WwiserHIRC`。

## 安装

```bash
pip install league-tools
```

如需基于发布分支安装最新代码：

```bash
pip install -e "git+https://github.com/Virace/league-tools@package#egg=league_tools"
```

## 使用

基础使用示例（四种核心格式）：

```python
from pathlib import Path

from league_tools import BIN, BNK, NativeHIRC, WAD, WPK

# 1) WPK：提取音频文件
wpk = WPK("path/to/audio.wpk")
wem_files = wpk.extract_files()

# 2) BNK：提取内嵌WEM
bnk = BNK("path/to/events.bnk")
bnk_wem_files = bnk.extract_files()

# 3) WAD：按已知路径提取文件
wad = WAD("path/to/archive.wad.client")
wad.extract(
    ["assets/sounds/vo/champions/gwen/skin01/vo_gwen_skin01_events.bnk"],
    out_dir=Path("./wad_output"),
)

# 4) BIN：读取音频事件组数据
bin_file = BIN("path/to/skin.bin")
audio_groups = bin_file.data

# 5) NativeHIRC：默认推荐的 events.bnk 解析入口
hirc = NativeHIRC.from_bnk("path/to/vo_events.bnk")
```

日志默认关闭；上游项目可按需手动开启：

```python
from league_tools import enable_logging, disable_logging

enable_logging()
# ... 业务逻辑 ...
disable_logging()
```

WAD 打包与替换（输出固定 v3.4）：

```python
from league_tools import WAD, WADBuilder

# 从零创建
WADBuilder() \
    .add('plugins/demo/config.json', b'{"enabled": true}') \
    .save('demo.wad.client')

# 打开已有 WAD，替换其中的文件后另存（output 省略则覆盖源文件）
wad = WAD('path/to/archive.wad.client')
wad.rebuild(
    {'plugins/demo/config.json': b'{"enabled": false}'},
    output='archive.modified.wad.client',
)
```

说明：`.bnk`/`.wpk` 原样存储，其余 zstd 压缩；头部签名置零（客户端不校验）。
注意游戏客户端更新/修复会按清单还原被修改的 WAD。

详细示例与格式文档：

- [基础 API 与快速上手](docs/api_basics.md)
- [格式总览](docs/formats_overview.md)
- [WAD 解析](docs/formats_wad.md)
- [BIN 解析](docs/formats_bin.md)
- [BNK 解析](docs/formats_bnk.md)
- [WPK 解析](docs/formats_wpk.md)
- [音频映射](docs/audio_mapping.md)
- [音频 Bank 事件解释（开发）](docs/audio_bank_parsing.md)

## 音频映射建议

默认工作流：

```python
from league_tools import AudioEventMapper, BIN, NativeHIRC

bin_file = BIN("path/to/skin.bin")
hirc = NativeHIRC.from_bnk("path/to/events.bnk")
mapping = AudioEventMapper(bin_file, hirc).build_mapping()
```

何时切到 `WwiserHIRC`：

- 需要完整 XML / HIRC 结构对照
- 需要调试 `wwiser` 输出或排查版本差异
- 需要的信息超出 `NativeHIRC` 当前只关注的音频事件映射范围

## 参考

- WPK 参考 [Morilli/bnk-extract](https://github.com/Morilli/bnk-extract)
- WAD 结构与部分逻辑来源于 [CommunityDragon/CDTB](https://github.com/CommunityDragon/CDTB) 与 [Pupix/lol-file-parser](https://github.com/Pupix/lol-file-parser)
- WAD v3.4 写入格式与存储策略对照了 [LeagueToolkit/cslol-manager](https://github.com/LeagueToolkit/cslol-manager)、[LeagueToolkit/LeagueToolkit](https://github.com/LeagueToolkit/LeagueToolkit) 与 [tarngaina/ltMAO](https://github.com/tarngaina/ltMAO) 的实现做佐证，未复制其代码
- BNK 结构参考 [Xentax Wiki](http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk))
- `NativeHIRC` 的 `MusicSwitch` / 音乐容器读取顺序在调试阶段参考了 [Neinndall/AssetsManager](https://github.com/Neinndall/AssetsManager) 的 BNK 解析实现，用于交叉校验 Wwise 145 样本的偏移处理
- `WwiserHIRC` 的 XML 对照与调试流程依赖 [bnnm/wwiser](https://github.com/bnnm/wwiser) 提供的导出能力；本项目将其作为外部分析工具使用，运行时需由用户自行提供可执行文件

## 维护

- 维护者：**Virace**（[孤独的未知数](https://x-item.com)）
- 开发与测试标准：[docs/development_testing.md](docs/development_testing.md)
- 发布与维护流程：[docs/release_workflow.md](docs/release_workflow.md)
- Wwise 黑箱转白箱可行性记录：[docs/wwise_reverse_engineering_feasibility.md](docs/wwise_reverse_engineering_feasibility.md)
- 许可证：[GPLv3](LICENSE)

## 感谢

- [@Morilli](https://github.com/Morilli/bnk-extract)（bnk-extract）
- [@Pupix](https://github.com/Pupix/lol-file-parser)（lol-file-parser）
- [@CommunityDragon](https://github.com/CommunityDragon/CDTB)（CDTB）
- [@Neinndall](https://github.com/Neinndall/AssetsManager)（AssetsManager，提供 BNK / 音乐容器解析对照思路）
- [@bnnm](https://github.com/bnnm/wwiser)（wwiser，提供 BNK XML 导出与结构对照能力）
- [@vgmstream](https://github.com/vgmstream/vgmstream)（vgmstream）
