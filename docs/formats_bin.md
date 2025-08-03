# BIN文件格式解析

## 概述

BIN文件相当于是英雄联盟中的配置文件，包含各种数据

## 文件结构

### 基本结构
```
BIN文件(音频部分)
├── 文件头 (PROP)
├── 皮肤音频属性 (可选)
├── 主题音乐数据 (皮肤文件特有)
└── 音频组列表
    ├── BANK_UNITS (银行单元集合)
    │   ├── 类别名称 (NAME)
    │   ├── 银行路径 (BANK_PATH)
    │   ├── 事件列表 (EVENTS)
    │   └── 其他属性
    └── MUSIC数据 (非皮肤文件)
```

### 数据类型

#### StringHash
存储事件名称和对应的FNV-1a哈希值：
```python
@dataclass
class StringHash:
    string: str          # 事件名称 (如 "Play_vo_Annie_Move1")
    hash: int           # FNV-1a哈希值
    container_id: int   # 容器ID (扩展用途)
    switch_id: int      # 切换ID (扩展用途)
    sound_index: int    # 声音索引 (扩展用途)
```

#### EventData
表示一个类别的事件数据：
```python
@dataclass
class EventData:
    category: str                    # 类别名称 (如 "Annie_Base_VO")
    events: List[StringHash]         # 该类别的事件列表
    bank_path: List[str]            # 对应的BNK文件路径
```

#### MusicData
存储音乐相关数据：
```python
@dataclass
class MusicData:
    theme_music_id: str                      # 主题音乐ID
    theme_music_transition_id: str           # 主题音乐过渡ID
    victory_music_id: str                    # 胜利音乐ID
    defeat_music_id: str                     # 失败音乐ID
    victory_banner_sound: str                # 胜利横幅音效
    defeat_banner_sound: str                 # 失败横幅音效
    ambient_event: str                       # 环境事件
    unknown_fields: Dict[int, str]           # 未知字段
```

#### AudioGroup
音频组，包含银行单元和音乐数据：
```python
@dataclass
class AudioGroup:
    bank_units: List[EventData]      # 银行单元列表
    music: Optional[MusicData]       # 音乐数据 (可选)
```

## 常量定义

常量数据来源于[CDTB](https://github.com/CommunityDragon/Data)

### 文件标识
```python
HEADER_SIGNATURE = b'PROP'                    # 文件头标记
SKIN_AUDIO_PROPERTIES = 0x8F7B194F           # 皮肤音频属性
THEME_MUSIC = 0x53ad3c01                     # 主题音乐标记
```

### 结构标记
```python
BANK_UNITS_SIGNATURE = [0x92, 0x9F, 0xF2, 0xF8]  # 银行单元集合
BANK_UNIT_SIGNATURE = 0xA4416515                   # 单个银行单元
MUSIC = 0x9f9c4fd4                                 # 音乐结构
```

### 字段标记
```python
NAME_SIGNATURE = 0x8D39BDE6                  # 名称字段
BANK_PATH_SIGNATURE = 0x2A21AD00             # 银行路径字段
EVENTS_SIGNATURE = 0x12D8E384                # 事件字段
VOICE_OVER_SIGNATURE = 0x3B13AA4B            # 语音覆盖字段
```

## 解析逻辑

### 文件类型检测
解析器首先检测文件类型：
```python
def _read(self):
    # 1. 验证文件头
    file_header = self._data.customize('<4s')
    if file_header != HEADER_SIGNATURE:
        raise ValueError('无效的文件头')
    
    # 2. 检测是否为皮肤文件
    skin_audio_pos = self._find_structure(SKIN_AUDIO_PROPERTIES)
    if skin_audio_pos != -1:
        self.is_skin = True
        # 处理主题音乐
        self._process_theme_music()
```

### 银行单元处理
解析BANK_UNITS结构：
```python
def _process_bank_units(self) -> List[EventData]:
    # 读取单元数量
    unit_count = self._data.customize('<I')
    
    events = []
    for i in range(unit_count):
        # 读取每个银行单元
        category = None
        bank_paths = []
        unit_events = []
        
        # 处理元素
        for element_mark in elements:
            if element_mark == EVENTS_SIGNATURE:
                # 读取事件列表
                for event_name in event_names:
                    hash_value = str_fnv_32(event_name)
                    unit_events.append(StringHash(event_name, hash_value))
```

### 音乐数据处理
非皮肤文件可能包含音乐数据：
```python
def _process_music_data(self) -> Optional[MusicData]:
    music_data = MusicData()
    field_count = self._data.customize('<H')
    
    # 字段映射
    field_mapping = {
        VICTORY_MUSIC_ID: 'victory_music_id',
        DEFEAT_MUSIC_ID: 'defeat_music_id',
        # ... 其他字段
    }
    
    # 解析每个字段
    for i in range(field_count):
        field_mark = self._data.customize('<I')
        value = self._data.string()
        
        attr_name = field_mapping.get(field_mark)
        if attr_name:
            setattr(music_data, attr_name, value)
```

## 使用方法

### 基础解析
```python
from league_tools.formats.bin import BIN

# 解析BIN文件
bin_file = BIN('annie_base.bin')

# 检查文件类型
print(f"是否为皮肤文件: {bin_file.is_skin}")
print(f"音频组数量: {len(bin_file.data)}")

# 遍历音频组
for i, audio_group in enumerate(bin_file.data):
    print(f"音频组 {i+1}:")
    print(f"  银行单元数量: {len(audio_group.bank_units)}")
    print(f"  包含音乐数据: {audio_group.music is not None}")
```

### 提取事件信息
```python
# 提取所有事件
all_events = []
for audio_group in bin_file.data:
    for bank_unit in audio_group.bank_units:
        print(f"类别: {bank_unit.category}")
        print(f"银行路径: {bank_unit.bank_path}")
        
        for event in bank_unit.events:
            all_events.append(event)
            print(f"  事件: {event.string} (Hash: {event.hash})")

print(f"总事件数量: {len(all_events)}")
```

### 按类别分组
```python
# 按类别组织事件
events_by_category = {}
for audio_group in bin_file.data:
    for bank_unit in audio_group.bank_units:
        category = bank_unit.category
        if category not in events_by_category:
            events_by_category[category] = []
        
        events_by_category[category].extend(bank_unit.events)

# 显示结果
for category, events in events_by_category.items():
    print(f"{category}: {len(events)} 个事件")
```

### 处理皮肤文件
```python
if bin_file.is_skin:
    print("皮肤文件特有信息:")
    print(f"主题音乐数量: {len(bin_file.theme_music)}")
    
    for i, theme in enumerate(bin_file.theme_music):
        print(f"  主题音乐 {i+1}: {theme}")
```

### 处理音乐数据
```python
# 查找包含音乐数据的音频组
for i, audio_group in enumerate(bin_file.data):
    if audio_group.music:
        music = audio_group.music
        print(f"音频组 {i+1} 的音乐数据:")
        print(f"  主题音乐ID: {music.theme_music_id}")
        print(f"  胜利音乐ID: {music.victory_music_id}")
        print(f"  失败音乐ID: {music.defeat_music_id}")
        
        if music.unknown_fields:
            print(f"  未知字段: {len(music.unknown_fields)} 个")
```

### 数据序列化
```python
# 转换为JSON
import json

# 单个事件数据
event_json = bin_file.data[0].bank_units[0].to_json()
print("事件数据JSON:", event_json)

# 整个音频组
audio_group_dict = bin_file.data[0].to_dict()
with open('audio_group.json', 'w', encoding='utf-8') as f:
    json.dump(audio_group_dict, f, ensure_ascii=False, indent=2)
```

### 哈希值计算
```python
from league_tools.utils.hash import str_fnv_32

# 手动计算事件名称的哈希值
event_name = "Play_vo_Annie_Move1"
calculated_hash = str_fnv_32(event_name)
print(f"事件 '{event_name}' 的哈希值: {calculated_hash}")

# 验证解析结果
for audio_group in bin_file.data:
    for bank_unit in audio_group.bank_units:
        for event in bank_unit.events:
            expected_hash = str_fnv_32(event.string)
            if event.hash != expected_hash:
                print(f"哈希值不匹配: {event.string}")
```

## 错误处理

### 常见异常
```python
try:
    bin_file = BIN('invalid_file.bin')
except FileNotFoundError:
    print("文件未找到")
except ValueError as e:
    print(f"文件格式错误: {e}")
except Exception as e:
    print(f"解析失败: {e}")
```

### 容错处理
```python
# 部分解析失败时的处理
bin_file = BIN('problematic_file.bin')

# 检查解析结果
if not bin_file.data:
    print("未找到任何音频组数据")
else:
    # 检查每个组的完整性
    for i, audio_group in enumerate(bin_file.data):
        if not audio_group.bank_units:
            print(f"音频组 {i+1} 没有银行单元")
        else:
            for j, bank_unit in enumerate(audio_group.bank_units):
                if not bank_unit.events:
                    print(f"银行单元 {j+1} 没有事件")
```

## 性能优化

### 大文件处理
```python
# 对于大型BIN文件，可以启用调试日志来监控解析进度
from loguru import logger

logger.add("bin_parsing.log", level="DEBUG")
bin_file = BIN('large_file.bin')
```

### 内存管理
```python
# 处理完成后清理资源
bin_file = BIN('file.bin')
# ... 处理数据 ...
del bin_file  # 显式删除以释放内存
```

## 扩展用法

### 自定义事件处理
```python
class CustomBINProcessor:
    def __init__(self, bin_file_path):
        self.bin_file = BIN(bin_file_path)
        self.event_stats = {}
    
    def analyze_events(self):
        """分析事件分布"""
        for audio_group in self.bin_file.data:
            for bank_unit in audio_group.bank_units:
                category = bank_unit.category
                event_count = len(bank_unit.events)
                
                if category not in self.event_stats:
                    self.event_stats[category] = 0
                self.event_stats[category] += event_count
        
        return self.event_stats
    
    def find_events_by_pattern(self, pattern: str):
        """根据模式查找事件"""
        matched_events = []
        for audio_group in self.bin_file.data:
            for bank_unit in audio_group.bank_units:
                for event in bank_unit.events:
                    if pattern.lower() in event.string.lower():
                        matched_events.append({
                            'category': bank_unit.category,
                            'event': event.string,
                            'hash': event.hash
                        })
        return matched_events

# 使用示例
processor = CustomBINProcessor('annie_base.bin')
stats = processor.analyze_events()
move_events = processor.find_events_by_pattern('move')
```

## 总结

BIN文件格式是英雄联盟音频系统的核心，通过解析BIN文件可以：

1. **获取音频事件映射关系** - 了解哪些事件对应哪些音频文件
2. **分析皮肤音频结构** - 区分VO（语音）和SFX（音效）
3. **提取音乐配置信息** - 获取胜利/失败音乐等配置
4. **支持音频工具开发** - 为音频提取和分析工具提供数据基础

该解析器具有良好的容错性和扩展性，能够处理各种版本的BIN文件格式。