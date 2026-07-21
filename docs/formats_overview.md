# 文件格式说明文档总览

本项目支持解析英雄联盟游戏中使用的四种主要文件格式，每种格式都有其特定的用途和特点。

快速上手与顶层 API 请先看：[API 基础用法](api_basics.md)

如果你在做音频事件映射开发，还可以配合阅读：[音频事件映射机制](audio_mapping.md) 和 [音频 Bank 事件解释（开发）](audio_bank_parsing.md)。

## 支持的文件格式

### 1. [BIN文件格式](formats_bin.md) 
**用途**: 皮肤音频事件和音乐数据存储  
**特点**: 
- 存储语音触发事件映射关系
- 支持皮肤文件和非皮肤文件
- 包含音乐配置信息
- 基于项目内事件哈希的索引

**主要数据结构**:
- `StringHash` - 事件名称和哈希值对
- `EventData` - 事件分类数据
- `MusicData` - 音乐配置信息
- `AudioGroup` - 音频组合容器

**适用场景**: 音频事件分析、语音提取、音频映射构建

---

### 2. [BNK文件格式](formats_bnk.md)
**用途**: Wwise音频引擎的音频资源文件  
**特点**:
- 包含音频层次结构(HIRC)
- 内嵌WEM音频文件
- 支持复杂的音频事件系统
- 多版本兼容(132, 134, 145)

**主要组件**:
- `BNK` - 基础BNK文件解析器
- `NativeHIRC` - 默认推荐的原生 HIRC 音频映射解析器
- `WwiserHIRC` - 高级HIRC解析器
- `Sound/Event/Action` - 音频对象类型
- `WemFile` - 音频文件容器

**适用场景**: 音频文件提取、事件系统分析、音频层次结构解析

---

### 3. [WAD文件格式](formats_wad.md)
**用途**: 英雄联盟游戏资源存档格式  
**特点**:
- 支持多种压缩算法(GZIP, Zstandard)
- 读取兼容 V1/V2/V3(含 3.4)，写入固定 v3.4
- 基于哈希的快速索引(路径哈希为小写路径的 xxh64)
- V3版本支持子块分割

**主要结构**:
- `WADSection` - 文件条目信息
- `WADBuilder` - 从零打包 v3.4 WAD
- `WAD.rebuild` - 打开已有 WAD 替换条目后全量重写
- 条目校验和(存储字节的 xxh3_64)

**适用场景**: 游戏资源提取、资源分析、批量文件操作、LCU 资源替换

---

### 4. [WPK文件格式](formats_wpk.md)
**用途**: 音频资源封装格式，专门用于WEM音频文件  
**特点**:
- 简洁的音频文件集合管理
- UTF-16编码文件名支持
- 专注于WEM音频格式
- 支持音频格式转换

**核心组件**:
- `WPK` - WPK文件解析器
- `WemFile` - WEM音频文件对象
- 文件名和数据分离存储
- 配合vgmstream进行格式转换

**适用场景**: 音频文件批量提取、音频格式转换、音频资源管理

## 格式对比

| 格式 | 主要用途 | 复杂度 | 压缩支持 | 特殊特性 |
|------|----------|--------|----------|----------|
| BIN  | 音频事件映射 | 中等 | 无 | 事件哈希索引、事件分类 |
| BNK  | 音频资源库 | 高 | 内嵌 | 层次结构、事件系统 |
| WAD  | 通用资源存档 | 高 | 多种 | 子块分割、版本演进 |
| WPK  | 音频文件封装 | 低 | 无 | UTF-16文件名、专注音频 |

## 使用建议

### 音频分析工作流
1. **BIN文件** → 获取事件名称和分类信息
2. **BNK文件** → 默认优先 `NativeHIRC` 解析事件映射所需的 HIRC 音频信息
3. **音频映射** → 使用`AudioEventMapper`构建事件-音频映射关系

如果需要更完整的 BNK/HIRC 结构、XML 对照或 wwiser 调试能力，再切到 `WwiserHIRC`。

### 资源提取工作流  
1. **WAD文件** → 提取游戏中的各类资源文件
2. **WPK文件** → 专门提取音频资源集合
3. **格式转换** → 使用vgmstream等工具转换音频格式

### 开发集成
```python
# 典型的音频处理流程
from league_tools.formats import BIN, BNK, NativeHIRC, WAD, WPK
from league_tools.tools import AudioEventMapper

# 1. 解析BIN文件获取事件信息
bin_file = BIN('annie_base.bin')

# 2. 默认推荐：直接解析 events.bnk 的音频事件结构
hirc = NativeHIRC.from_bnk('annie_base_vo_events.bnk')

# 3. 构建事件-音频映射
mapper = AudioEventMapper(bin_file, hirc)
mapping = mapper.build_mapping()

# 4. 从WAD文件中提取资源
wad = WAD('game_data.wad')
wad.extract(['path/to/audio/file.bnk'], 'extracted/')

# 5. 处理WPK音频包
wpk = WPK('audio_pack.wpk')
wem_files = wpk.extract_files()
```

## 错误处理策略

所有格式解析器都提供了专门的异常类型，建议采用分层错误处理：

```python
try:
    # 文件解析操作
    parser = FileParser('file.ext')
except FileFormatSpecificHeaderError:
    # 处理文件头错误（通常表示格式不匹配）
    pass
except FileFormatSpecificError:
    # 处理格式特定错误
    pass
except FileNotFoundError:
    # 处理文件不存在
    pass
except Exception as e:
    # 处理其他未预期错误
    pass
```

## 性能考虑

1. **大文件处理**: 所有解析器都支持流式处理以减少内存占用
2. **解析路径选择**: 映射主链优先 `NativeHIRC`；需要完整结构或 XML 对照时使用 `WwiserHIRC`
3. **并发处理**: 支持多线程批量处理多个文件
4. **内存管理**: 提供资源清理接口避免内存泄漏

## 扩展开发

项目结构支持轻松扩展新的文件格式：

1. 继承`SectionBase`或`SectionNoId`基类
2. 实现`_read()`方法定义解析逻辑
3. 定义数据结构类(`@dataclass`)
4. 添加相应的异常类型
5. 编写完整的使用文档

每种格式的详细说明、代码示例和最佳实践请参考对应的格式文档。
