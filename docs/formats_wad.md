# WAD 文件格式解析

## 概述

WAD 文件是英雄联盟使用的资源存档格式，类似 ZIP 压缩包，用于打包游戏资源（模型、贴图、音频、配置等）。库提供两个方向的能力：

- **读取**：兼容 v1 / v2 / v3（含 v3.4）的解析与提取（`WAD`）。
- **写入**：从零打包（`WADBuilder`）与打开已有 WAD 替换条目（`WAD.rebuild`），输出固定为 **v3.4**。

## 文件结构

### 基本布局

```
WAD 文件
├── 文件头（含标识 RW、版本号、条目数量；v2/v3 另有签名与校验和字段）
├── 条目表 TOC（按 path_hash 升序，客户端依赖二分查找）
│   ├── 条目1（路径哈希、偏移、大小、类型、校验和等）
│   └── ...
└── 数据区
    ├── 条目数据（按类型可能压缩；重复内容可被多个条目共享）
    └── ...
```

### 头部版本差异

| 版本 | 头部内容 | 头部大小 | 条目大小 |
|------|----------|----------|----------|
| v1 | `RW` + 版本 + 条目表偏移(u16) + 条目大小(u16) + 数量(u32) | 12 | 24 |
| v2 | `RW` + 版本 + 变长 ECDSA 签名(84 字节区) + 校验和(u64) + 条目表偏移/大小 + 数量(u32) | 104 | 32 |
| v3.x | `RW` + 版本 + ECDSA 签名(256) + 校验和(u64) + 数量(u32) | 272 | 32 |

### 条目布局

v1（24 字节）：`path_hash(u64) + offset(u32) + compressed_size(u32) + size(u32) + type(u32)`

v3.0–3.3（32 字节）：

```
path_hash(u64) + offset(u32) + compressed_size(u32) + size(u32)
+ type字节(低4位类型/高4位子块数) + duplicate(u8) + subchunk_index(u16) + checksum(u64)
```

v3.4（32 字节，当前游戏使用）：

```
path_hash(u64) + offset(u32) + compressed_size(u32) + size(u32)
+ type字节(低4位类型/高4位子块数) + subchunk_index(24位混合端序) + checksum(u64)
```

v3.4 与 v3.0–3.3 的关键差异：**没有 duplicate 标志字节**，该字节并入了 24 位 subchunk_index（磁盘字节序 `[hi][lo][mi]`）；重复内容仅表现为多个条目共享同一 offset。

## 数据结构

### WADSection（文件条目）

```python
@dataclass
class WADSection:
    path_hash: int              # 路径哈希（xxh64）
    offset: int                 # 数据在文件中的偏移
    compressed_size: int        # 存储大小
    size: int                   # 解压后大小
    type: int                   # 存储类型（低4位）
    duplicate: bool = False     # 重复条目标志（v3.4 无此字段，恒为 False）
    first_subchunk_index: Optional[int] = None  # 子块起始索引
    sha256: Optional[int] = None                # 条目校验和（见下文哈希说明）

    # __post_init__ 派生
    subchunk_count: int         # 子块数量（type 字节高4位）
    path: Optional[str]         # 外部哈希表解析出的明文路径
```

### 存储类型

| 值 | 含义 | 说明 |
|----|------|------|
| 0 | 无压缩 | 原样存储 |
| 1 | gzip | 旧版使用，现已淘汰 |
| 2 | 文件重定向 | 数据区存目标路径字符串，提取时返回 `None` |
| 3 | zstd | 当前主流压缩方式 |
| 4 | 子块 zstd | 数据区内联子块：每块 8 字节头（压缩大小 u32 + 解压大小 u32）+ 数据；压缩大小等于解压大小时该块未压缩，否则为 zstd |

## 哈希说明

WAD 涉及两种不同用途的哈希，不要混淆：

- **路径哈希**（条目标识）：小写路径的 `xxh64`，**所有版本一致**。即 `WAD.get_hash(path)`。
- **条目校验和**（`WADSection.sha256` 字段）：条目**存储字节**的 `xxh3_64`。字段名 `sha256` 为历史命名，实际不是 SHA-256。

WAD 内部只保存路径哈希，不保存明文路径；按目录还原真实路径依赖外部哈希表（如 CommunityDragon 的 hashes 文件）。

## 使用方法

### 解析与遍历

```python
from league_tools import WAD

wad = WAD('archive.wad.client')

print(f"版本: {wad.version}")        # 如 [3, 4]
print(f"条目数量: {wad.file_count}")
print(f"头部大小: {wad.header_size}")

for section in wad.files:
    print(f"{section.path_hash:016x} 类型={section.type} "
          f"大小={section.size}(存储 {section.compressed_size}) "
          f"子块={section.subchunk_count}")
```

### 按路径提取

```python
paths = [
    'assets/characters/ahri/skins/base/audio/ahri_base_vo_events.bnk',
    'plugins/rcp-be-lol-game-data/global/default/v1/champion-choose-vo/1.ogg',
]

# 落盘
wad.extract(paths, out_dir='extracted/')

# 或直接取字节（不落盘）
datas = wad.extract(paths, raw=True)   # 未命中的路径对应 None
```

### 按条目提取

```python
for section in wad.files:
    if section.size > 1024 * 1024:
        wad.extract_by_section(section, f'large/{section.path_hash:016x}.dat')
```

### 按哈希表提取

`extract_hash` 的键是**路径哈希的十进制字符串**，值是输出相对路径：

```python
hashtable = {
    '4364587749292437910': 'assets/sounds/music/champion_select.ogg',
}
extracted = wad.extract_hash(hashtable, out_dir='extracted_by_hash/')
```

### 路径哈希计算

```python
path = 'assets/characters/ahri/skins/base/audio/events.bnk'
path_hash = WAD.get_hash(path)   # 小写路径的 xxh64，所有版本一致

section = next((f for f in wad.files if f.path_hash == path_hash), None)
```

### 打包（WADBuilder）

从零创建 WAD，输出固定 v3.4：

```python
from league_tools import WADBuilder

builder = WADBuilder()
builder.add('plugins/demo/config.json', b'{"enabled": true}')
builder.add('assets/sounds/demo.bnk', 'local/demo.bnk')   # 也接受本地文件路径
builder.add_by_hash(0x1234567890ABCDEF, b'...')           # 明文路径未知时按哈希添加

builder.save('demo.wad.client')     # 写文件（临时文件 + 原子替换）
data = builder.to_bytes()           # 或直接取完整字节
```

写入行为：

- TOC 按 path_hash 升序；同一路径/哈希重复添加时后写覆盖。
- 压缩策略默认按扩展名：`.bnk`/`.wpk` 原样存储（type 0，Wwise 容器已压缩），其余 zstd（type 3）；`add(..., compression='raw'/'zstd')` 可显式指定。不生成 type 1/2/4。
- 相同存储内容只写一份数据，多个条目共享 offset。
- 头部 ECDSA 签名与校验和全零（客户端不校验，已在真实 LCU 环境验证）。

### 替换（WAD.rebuild）

打开已有 WAD，替换其中的条目后全量重写：

```python
wad = WAD('archive.wad.client')

wad.rebuild(
    {
        'plugins/demo/config.json': b'{"enabled": false}',  # 按路径
        0x9876543210FEDCBA: 'local/new_file.bin',           # 或按哈希，值也可为本地文件路径
    },
    output='archive.modified.wad.client',   # 省略则覆盖源文件（对象自动重新打开）
    strict=True,                            # 替换目标不存在时抛 KeyError；False 则跳过并告警
)
```

替换行为：

- 未替换条目按存储字节原样搬运（不解压重压），type/subchunk/校验和保留，仅重算 offset；共享数据的条目在新文件中继续共享。
- 替换条目沿用**原条目的存储方式**（原条目未压缩则原样存储，其余按扩展名策略压缩），重算大小与校验和，subchunk 字段清零。
- 输出版本恒为 v3.4（输入可为任意可读版本）。
- 写入走同目录临时文件 + 原子替换，中途失败不破坏目标文件。

注意：游戏客户端更新/修复会按清单校验并还原被修改的 WAD，这是客户端行为，与文件格式无关。

## 错误处理

```python
import struct

from league_tools import WAD
from league_tools.formats.wad.parser import MalformedSubchunkError

try:
    wad = WAD('archive.wad.client')
except ValueError as e:
    print(f'文件头或版本不支持: {e}')     # 非 RW 标识、主版本 > 3
except FileNotFoundError:
    print('文件不存在')

for section in wad.files:
    data = wad.extract_by_section(section, '', raw=True)
    # 解压失败、type 2 重定向均返回 None；子块损坏在内部以 MalformedSubchunkError 捕获
```

`rebuild` 相关异常：

- `KeyError`：`strict=True` 且替换目标不存在。
- `ValueError`：WAD 从 bytes/流打开且未指定 `output`。

## 总结

1. **读取** 兼容 v1/v2/v3（含 v3.4），支持无压缩、gzip、zstd、子块 zstd 与重定向条目。
2. **写入** 固定 v3.4：`WADBuilder` 从零打包，`WAD.rebuild` 替换已有条目，均保证 TOC 有序、数据去重、原子落盘。
3. **哈希**：路径哈希为小写路径 `xxh64`（全版本一致）；条目校验和为存储字节 `xxh3_64`（字段名 `sha256` 系历史命名）。
4. 明文路径还原依赖外部哈希表，WAD 本体只存哈希。
