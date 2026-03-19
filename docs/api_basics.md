# API 基础用法

本文提供 `league-tools` 对外 API 的最小使用方式。复杂参数、进阶场景与边界处理请参考各格式专门文档。

## 1. 对外入口

顶层可直接导入：

```python
from league_tools import (
    BIN,
    BNK,
    NativeHIRC,
    WPK,
    WAD,
    WwiserHIRC,
    WwiserManager,
    AudioEventMapper,
    AudioMapping,
    MappingAnalyzer,
    enable_logging,
    disable_logging,
    is_logging_enabled,
)
```

音频事件映射默认推荐 `NativeHIRC`；如果你需要完整 XML/HIRC 结构或调试信息，再切到 `WwiserHIRC`。

## 2. 四种格式最小示例

```python
from pathlib import Path

from league_tools import BIN, BNK, WAD, WPK

# WPK: 提取 WEM 文件
wpk = WPK("path/to/audio.wpk")
wem_files = wpk.extract_files()

# BNK: 提取内嵌 WEM 文件
bnk = BNK("path/to/events.bnk")
bnk_wem_files = bnk.extract_files()

# WAD: 按已知资源路径提取
wad = WAD("path/to/archive.wad.client")
wad.extract(
    ["assets/sounds/vo/champions/gwen/skin01/vo_gwen_skin01_events.bnk"],
    out_dir=Path("./wad_output"),
)

# BIN: 读取音频组信息
bin_file = BIN("path/to/skin.bin")
audio_groups = bin_file.data
```

## 3. 日志控制（默认关闭）

库默认关闭 `league_tools` 命名空间日志输出。

```python
from league_tools import disable_logging, enable_logging, is_logging_enabled

print(is_logging_enabled())  # False
enable_logging()
print(is_logging_enabled())  # True
disable_logging()
```

## 4. 进阶文档

- [格式总览](formats_overview.md)
- [WAD 解析](formats_wad.md)
- [BIN 解析](formats_bin.md)
- [BNK 解析](formats_bnk.md)
- [WPK 解析](formats_wpk.md)
- [音频映射机制](audio_mapping.md)
- [音频 Bank 事件解释（开发）](audio_bank_parsing.md)
- [开发测试说明](development_testing.md)
- [发布维护流程](release_workflow.md)
