# BNK文件格式解析

## 概述

BNK（Bank）文件是 Wwise 音频引擎使用的音频资源文件格式，包含了音频数据、音频层次结构（HIRC）和相关元数据。在英雄联盟中，BNK 文件存储了游戏的音频文件和事件映射关系。

本仓当前有两条 HIRC 路径：

- `NativeHIRC`：默认推荐，只关注音频事件映射所需的 HIRC 信息，直接从 `events.bnk` 读取，速度更快
- `WwiserHIRC`：需要完整 XML / HIRC 结构、wwiser 对照或调试时再使用

## 文件结构

### 基本格式
```
BNK文件
├── BKHD (Bank Header) - 文件头信息
├── DIDX (Data Index) - 音频文件索引 (可选)
├── DATA - 音频文件数据 (可选)
├── HIRC (Hierarchy) - 音频层次结构
└── 其他区块...
```

### 数据流程
```text
.bnk文件 → NativeHIRC → 音频事件映射
        ↘ wwiser.pyz → XML文件 → WwiserHIRC（完整结构 / 调试）
```

`BNK` 本体仍然只处理 `BKHD / DIDX / DATA`，主要负责解包与提取内嵌 WEM；事件映射场景下默认优先 `NativeHIRC`。

## 核心组件

### 1. BNK解析器
直接解析BNK文件的基础结构：

```python
class BNK(SectionNoId):
    """
    Wwise BNK文件解析器
    支持的版本: 132, 134, 145
    """
    
    # 主要属性
    _bkhd_section: BKHD      # 文件头
    _didx_section: DIDX      # 数据索引
    _data_section: DATA      # 数据区块
    _files: List[WemFile]    # WEM文件列表
    is_compatible: bool      # 版本兼容性
```

### 2. NativeHIRC 解析器
默认推荐的原生音频映射解析器：

```python
class NativeHIRC:
    """
    直接从 events.bnk 读取音频事件映射所需的 HIRC 信息
    不追求完整 BNK/HIRC 结构，只关注音频相关对象
    """
```

适用场景：

- 默认音频映射主链
- 批量事件分析
- 对性能敏感的真实样本处理

### 3. WwiserHIRC解析器
基于 wwiser 工具的高级解析器：

```python
class WwiserHIRC:
    """
    基于wwiser XML的HIRC兼容对象
    支持缓存和多文件处理
    """
    
    # 核心功能
    - XML解析和对象创建
    - 两级缓存系统
    - 音频层次结构分析
    - 事件-音频映射构建
```

## 区块详解

### BKHD (Bank Header)
存储BNK文件的元数据：

```python
@dataclass
class BKHD:
    bank_version: int        # 资源库生成器版本 (如 145)
    soundbank_id: int        # 音频资源库ID
    language_id: int         # 语言ID
    alignment: int           # 对齐值 (通常16)
    device_allocated: bool   # 设备分配标志
    project_id: int          # 项目ID
    soundbank_type: int      # 音频资源库类型
    bank_hash: bytes         # 16字节哈希值
```

### DIDX (Data Index)
WEM文件的索引信息：

```python
@dataclass
class WemFile:
    id: int                  # WEM文件ID
    offset: int              # 在DATA区块中的偏移
    length: int              # 文件长度
    filename: str            # 文件名 (可选)
    data: bytes              # 文件数据 (从DATA区块读取)
```

### HIRC对象类型
音频层次结构中的对象类型：

```python
class HIRCType(IntEnum):
    SOUND = 2                      # 声音对象
    ACTION = 3                     # 动作对象
    EVENT = 4                      # 事件对象
    RANDOM_CONTAINER = 5           # 随机容器
    SWITCH_CONTAINER = 6           # 切换容器
    MUSIC_SEGMENT_CONTAINER = 10   # 音乐段容器
    MUSIC_TRACK = 11               # 音乐轨道
    MUSIC_SWITCH_CONTAINER = 12    # 音乐切换容器
    MUSIC_RANDOM_CONTAINER = 13    # 音乐随机容器
```

#### Sound对象
```python
@dataclass
class Sound:
    object_id: int          # 对象ID
    source_id: int          # 音频源ID (对应WEM文件ID)
    stream_type: int        # 流类型
```

#### Event对象
```python
@dataclass
class Event:
    object_id: int          # 事件ID
    event_ids: List[int]    # 关联的动作ID列表
```

#### Action对象
```python
@dataclass
class Action:
    object_id: int          # 动作ID
    action_type: int        # 动作类型
    id_ext: int            # 目标对象ID
    # 特殊类型的额外属性
    switch_group_id: int    # 切换组ID (SetSwitch类型)
    switch_state_id: int    # 切换状态ID (SetSwitch类型)
    state_group_id: int     # 状态组ID (SetState类型)
    target_state_id: int    # 目标状态ID (SetState类型)
```

## 使用方法

### 基础BNK解析
```python
from league_tools.formats.bnk import BNK

# 解析BNK文件
try:
    bnk = BNK('events.bnk')
    
    # 检查兼容性
    if not bnk.is_version_supported():
        print(f"警告: BNK版本 {bnk.get_soundbank_version()} 可能不完全支持")
    
    # 获取基本信息
    print(f"资源库ID: {bnk.get_soundbank_id()}")
    print(f"版本: {bnk.get_soundbank_version()}")
    print(f"语言ID: {bnk.get_language_id()}")
    
    # 提取内嵌音频文件
    wem_files = bnk.extract_files()
    print(f"包含 {len(wem_files)} 个WEM文件")
    
    for wem_file in wem_files:
        print(f"  WEM ID: {wem_file.id}, 大小: {wem_file.length} 字节")
        
        # 保存WEM文件
        if wem_file.data:
            wem_file.save_file(f"output/{wem_file.id}.wem")

except BNKHeaderError:
    print("不是有效的BNK文件")
except BNKVersionError as e:
    print(f"版本不兼容: {e}")
except BNKFormatError as e:
    print(f"文件格式错误: {e}")
```

### 使用 NativeHIRC 解析（默认推荐）
```python
from league_tools import NativeHIRC

hirc = NativeHIRC.from_bnk('events.bnk')
```

说明：

- `NativeHIRC` 只解析音频事件映射所需的 HIRC 音频信息
- 它不是完整 BNK 解析器，也不输出 wwiser 的完整 XML 结构
- 如果你只想做 `event -> wemId[]` 映射，优先使用它

### 使用 WwiserHIRC 解析
```python
from league_tools.formats.bnk import WwiserHIRC
from league_tools.utils.wwiser import WwiserManager

# 初始化管理器
wm = WwiserManager()

# 方式1: 直接从BNK文件
hirc = WwiserHIRC.from_bnk('events.bnk', wwiser_manager=wm)

# 方式2: 从已有XML文件
hirc = WwiserHIRC.from_xml('events.xml')

# 方式3: 灵活初始化
hirc = WwiserHIRC()
hirc.load_file('events.bnk', wwiser_manager=wm)
```

### 缓存管理
```python
# 自定义缓存目录
hirc = WwiserHIRC.from_bnk(
    'events.bnk',
    cache_dir='custom_cache',
    use_cache=True,
    wwiser_manager=wm
)

# 禁用缓存
hirc = WwiserHIRC.from_bnk(
    'events.bnk',
    use_cache=False,
    wwiser_manager=wm
)

# 缓存原理：
# BNK -> XML (wwiser工具转换，基于BNK文件mtime缓存)
# XML -> HIRC对象 (解析缓存，基于BNK文件属性)
```

### 音频对象查询
```python
# 获取资源库列表
bank_names = hirc.get_bank_names()
print(f"包含的资源库: {bank_names}")

# 查询特定事件
event_id = 123456789
event = hirc.get_event(event_id)
if event:
    print(f"事件 {event_id}:")
    print(f"  关联动作: {event.event_ids}")

# 查询特定声音
sound_id = 987654321
sound = hirc.get_sound(sound_id)
if sound:
    print(f"声音 {sound_id}:")
    print(f"  音频源ID: {sound.source_id}")
    print(f"  流类型: {sound.stream_type}")

# 遍历特定银行的所有对象
bank = hirc['events']
if bank:
    print(f"银行 'events' 统计: {bank.stats()}")
    print(f"  事件数量: {len(bank.events)}")
    print(f"  声音数量: {len(bank.sounds)}")
    print(f"  动作数量: {len(bank.actions)}")
```

### 构建音频映射
```python
from league_tools.tools import AudioEventMapper
from league_tools import BIN, NativeHIRC

bin_file = BIN('annie_base.bin')
hirc = NativeHIRC.from_bnk('annie_base_vo_events.bnk')

mapper = AudioEventMapper(bin_file, hirc)
mapping = mapper.build_mapping()

# 查询映射关系
event_name = "Play_vo_Annie_Move1"
sound_ids = mapping.find_sounds_by_event_name(event_name)
print(f"事件 '{event_name}' 对应的音频ID: {sound_ids}")

# 反向查询
sound_id = 123456
events = mapping.find_events_by_sound_id(sound_id)
print(f"音频ID {sound_id} 被以下事件使用: {events}")
```

### 高级查询示例
```python
class BNKAnalyzer:
    def __init__(self, bnk_path, wwiser_manager):
        self.bnk = BNK(bnk_path)
        self.hirc = WwiserHIRC.from_bnk(bnk_path, wwiser_manager=wwiser_manager)
    
    def analyze_audio_structure(self):
        """分析音频结构"""
        results = {}
        
        # 基础信息
        results['basic_info'] = {
            'soundbank_id': self.bnk.get_soundbank_id(),
            'version': self.bnk.get_soundbank_version(),
            'wem_count': len(self.bnk.extract_files()),
            'banks': self.hirc.get_bank_names()
        }
        
        # 统计各类型对象数量
        total_stats = {}
        for bank_name in self.hirc.get_bank_names():
            bank = self.hirc[bank_name]
            if bank:
                stats = bank.stats()
                for key, value in stats.items():
                    total_stats[key] = total_stats.get(key, 0) + value
        
        results['hirc_stats'] = total_stats
        return results
    
    def find_broken_references(self):
        """查找损坏的引用关系"""
        broken_refs = []
        
        for bank_name in self.hirc.get_bank_names():
            bank = self.hirc[bank_name]
            if not bank:
                continue
            
            # 检查事件->动作引用
            for event in bank.events.values():
                for action_id in event.event_ids:
                    if action_id not in bank.actions:
                        broken_refs.append(f"事件 {event.object_id} 引用了不存在的动作 {action_id}")
            
            # 检查动作->目标引用
            for action in bank.actions.values():
                target_id = action.id_ext
                if target_id and target_id not in bank.sounds and target_id not in bank.random_containers:
                    broken_refs.append(f"动作 {action.object_id} 引用了不存在的目标 {target_id}")
        
        return broken_refs

# 使用分析器
analyzer = BNKAnalyzer('events.bnk', wm)
analysis = analyzer.analyze_audio_structure()
broken_refs = analyzer.find_broken_references()

print("BNK文件分析结果:")
print(f"  基础信息: {analysis['basic_info']}")
print(f"  HIRC统计: {analysis['hirc_stats']}")
if broken_refs:
    print(f"  发现 {len(broken_refs)} 个损坏的引用")
```

## 错误处理

### BNK解析错误
```python
from league_tools.formats.bnk import (
    BNKHeaderError, BNKFormatError, 
    BNKVersionError, BNKSectionError
)

try:
    bnk = BNK('file.bnk')
except BNKHeaderError:
    print("文件不是有效的BNK格式")
except BNKVersionError as e:
    print(f"BNK版本不支持: {e}")
except BNKSectionError as e:
    print(f"区块解析失败: {e.section_name} - {e}")
except BNKFormatError as e:
    print(f"文件格式错误: {e}")
```

### WwiserHIRC错误
```python
from league_tools.formats.bnk.wwiser import (
    WwiserError, WwiserXmlError, 
    WwiserCacheError, WwiserObjectError
)

try:
    hirc = WwiserHIRC.from_bnk('events.bnk', wwiser_manager=wm)
except WwiserXmlError as e:
    print(f"XML解析失败: {e}")
except WwiserCacheError as e:
    print(f"缓存操作失败: {e}")
except WwiserObjectError as e:
    print(f"对象创建失败: {e}")
```

## 性能优化

### 缓存策略
```python
# 1. 优化缓存目录
import os
cache_dir = os.path.expanduser('~/.league-tools/cache')
hirc = WwiserHIRC.from_bnk('events.bnk', cache_dir=cache_dir, wwiser_manager=wm)

# 2. 批处理多个文件
wm = WwiserManager()
hircs = []

bnk_files = ['events1.bnk', 'events2.bnk', 'events3.bnk']
for bnk_file in bnk_files:
    hirc = WwiserHIRC.from_bnk(bnk_file, wwiser_manager=wm)
    hircs.append(hirc)

# 3. 内存管理
hirc.clear()  # 清空已加载的数据
del hirc      # 释放内存
```

### 大文件处理
```python
# 对于大型BNK文件，启用详细日志
from loguru import logger

logger.add("bnk_processing.log", level="DEBUG")

# 分步处理
hirc = WwiserHIRC()
success = hirc.load_file('large_events.bnk', wwiser_manager=wm)
if success:
    print("文件加载成功")
else:
    print("文件加载失败，检查日志")
```

## 扩展应用

### 音频文件提取工具
```python
class AudioExtractor:
    def __init__(self, bnk_path, output_dir):
        self.bnk = BNK(bnk_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def extract_all_wem(self):
        """提取所有WEM文件"""
        wem_files = self.bnk.extract_files()
        
        for wem_file in wem_files:
            if wem_file.data:
                output_path = self.output_dir / f"{wem_file.id}.wem"
                wem_file.save_file(output_path)
                print(f"已提取: {wem_file.id}.wem ({wem_file.length} 字节)")
    
    def extract_by_ids(self, target_ids):
        """根据ID提取特定文件"""
        wem_files = self.bnk.extract_files()
        
        for wem_file in wem_files:
            if wem_file.id in target_ids and wem_file.data:
                output_path = self.output_dir / f"{wem_file.id}.wem"
                wem_file.save_file(output_path)
                print(f"已提取目标文件: {wem_file.id}.wem")

# 使用提取器
extractor = AudioExtractor('events.bnk', 'extracted_audio')
extractor.extract_all_wem()
```

### BNK文件信息查看器
```python
class BNKInspector:
    def __init__(self, bnk_path):
        self.bnk_path = bnk_path
        self.bnk = BNK(bnk_path)
        self.wm = WwiserManager()
        
    def generate_report(self):
        """生成详细报告"""
        report = []
        report.append(f"BNK文件报告: {self.bnk_path}")
        report.append("=" * 50)
        
        # 基础信息
        report.append("基础信息:")
        report.append(f"  资源库ID: {self.bnk.get_soundbank_id()}")
        report.append(f"  版本: {self.bnk.get_soundbank_version()}")
        report.append(f"  语言ID: {self.bnk.get_language_id()}")
        report.append(f"  兼容性: {'兼容' if self.bnk.is_version_supported() else '不兼容'}")
        
        # WEM文件信息
        wem_files = self.bnk.extract_files()
        total_size = sum(wem.length for wem in wem_files)
        report.append(f"\nWEM文件:")
        report.append(f"  数量: {len(wem_files)}")
        report.append(f"  总大小: {total_size:,} 字节")
        
        # 尝试加载HIRC信息
        try:
            hirc = WwiserHIRC.from_bnk(self.bnk_path, wwiser_manager=self.wm)
            report.append(f"\nHIRC信息:")
            report.append(f"  银行数量: {len(hirc.get_bank_names())}")
            
            for bank_name in hirc.get_bank_names():
                bank = hirc[bank_name]
                if bank:
                    stats = bank.stats()
                    report.append(f"  银行 '{bank_name}':")
                    for key, value in stats.items():
                        report.append(f"    {key}: {value}")
        
        except Exception as e:
            report.append(f"\nHIRC解析失败: {e}")
        
        return "\n".join(report)

# 使用检查器
inspector = BNKInspector('events.bnk')
report = inspector.generate_report()
print(report)

# 保存报告
with open('bnk_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)
```

## 总结

BNK文件格式是Wwise音频系统的核心，提供了完整的音频资源管理功能：

1. **多层次解析能力** - 从基础BNK结构到高级HIRC层次
2. **灵活的缓存机制** - 支持XML转换缓存和对象解析缓存  
3. **完整的错误处理** - 针对不同错误类型的专门异常
4. **版本兼容性检查** - 支持多个Wwise版本
5. **音频文件提取** - 直接提取内嵌的WEM音频文件
6. **事件映射构建** - 配合BIN文件构建完整的音频事件系统

该解析器为英雄联盟音频分析和处理工具提供了强大的基础支持。
