# 音频事件映射机制

## 概述

音频事件映射是将 BIN 文件中的事件名称（如 `Play_vo_Aurora_Move1`）映射到 BNK/WPK 中具体音频文件 ID 的过程。这个映射通过 Wwise 的层级容器结构实现。

默认推荐使用 `NativeHIRC` 作为 HIRC 来源：

- 直接从 `events.bnk` 读取音频映射所需信息
- 不依赖 `wwiser -> XML`
- 更适合批量映射和真实样本分析

如果需要更完整的 BNK/HIRC 结构或 XML 对照，再切到 `WwiserHIRC`。

当前 `NativeHIRC` 与 `WwiserHIRC` 都支持以下几类基础映射链路：

- `Event -> Action -> Sound`
- `Event -> Action -> RandomContainer / SwitchContainer -> Sound`
- `Event -> Action -> MusicSwitchContainer -> MusicRandomContainer -> MusicSegment -> MusicTrack -> source_id`

最终资源 ID 与导出后的文件命名是一致的：

```text
source_id == <source_id>.wem
```

新版本采用了模块化设计，将功能分为三个核心类：
- **AudioMapping**: 数据存储和查询
- **AudioEventMapper**: 映射构建器
- **MappingAnalyzer**: 数据分析器

## 映射路径

```
事件名称 → Event → Action → [容器层级] → Sound / MusicTrack → 音频文件ID
```

## 详细映射流程

### 1. 起始点：BIN文件中的事件字符串

```
StringHash对象
├── string: "Play_vo_Aurora_Move1"  (事件名称)
└── hash: 123456789                (与项目实现一致的 32-bit 事件哈希)
```

### 2. 查找Event对象

通过事件ID在HIRC中查找对应的Event对象：

```
Event (HIRCType.EVENT = 4)
├── object_id: 123456789
└── event_ids: [987654321, 876543210]  (关联的Action ID列表)
```

### 3. 遍历Action对象

对每个Action ID查找对应的Action对象：

```
Action (HIRCType.ACTION = 3)
├── object_id: 987654321
├── action_type: 4 (Play动作)
└── id_ext: 555666777  (目标对象ID)
```

**Action类型说明：**
- `4`: Play - 播放音频
- `25`: SetSwitch - 设置切换状态
- `18`: SetState - 设置全局状态

### 4. 容器层级遍历

目标对象可能是：

#### 4.1 直接的Sound对象
```
Sound (HIRCType.SOUND = 2)
├── object_id: 555666777
├── source_id: 12345        # 最终的音频文件ID
└── stream_type: 0
```

#### 4.2 随机容器 (RandomContainer)
```
RanSeqCntr (HIRCType.RANDOM_CONTAINER = 5)
├── object_id: 555666777
├── direct_parent_id: 444555666
└── child_ids: [11111, 22222, 33333]  # 包含多个子Sound
```

#### 4.3 切换容器 (SwitchContainer)
```
SwitchCntr (HIRCType.SWITCH_CONTAINER = 6)
├── object_id: 555666777
├── direct_parent_id: 444555666
└── child_ids: [44444, 55555, 66666]  # 根据切换状态选择
```

#### 4.4 音乐切换容器 (MusicSwitchContainer)
```
MusicSwitchCntr (HIRCType.MUSIC_SWITCH_CONTAINER = 12)
├── object_id: 555666777
├── direct_parent_id: 444555666
└── child_ids: [70001, 70002, 70003]  # 下游通常接 MusicRandom / MusicSegment
```

说明：

- `MusicSwitch` 内部还存在 `rules / nodes / arguments / transition` 等结构。
- 对事件映射来说，最关键的是先恢复可遍历的下游节点链路，再继续走到最终资源 ID。
- `WwiserHIRC` 当前从下面这个 XML 位置提取可遍历的目标节点：

```text
.//list[@name='pNodes']//field[@name='audioNodeId']
```

对应的 `wwiser` XML 树通常是：

```text
CAkMusicSwitchCntr
└── MusicSwitchCntrInitialValues
    └── pNodes
        └── audioNodeId
```

#### 4.5 音乐随机/播放列表容器 (MusicRandom / Playlist)
```
MusicRandomCntr (HIRCType.MUSIC_RANDOM_CONTAINER = 13)
├── object_id: 70001
├── direct_parent_id: 555666777
└── child_ids: [80001, 80002]  # 下游通常接 MusicSegment
```

`WwiserHIRC` 当前从下面这个 XML 位置提取 `SegmentID` 作为 `child_ids`：

```text
.//list[@name='pPlayList']//field[@name='SegmentID']
```

对应树形位置：

```text
CAkMusicRanSeqCntr
└── MusicRanSeqCntrInitialValues
    └── pPlayList
        └── SegmentID
```

#### 4.6 音乐段容器 (MusicSegment)
```
MusicSegmentCntr (HIRCType.MUSIC_SEGMENT_CONTAINER = 10)
├── object_id: 80001
├── direct_parent_id: 70001
└── child_ids: [90001, 90002]  # 下游接 MusicTrack
```

`WwiserHIRC` 当前直接从 `MusicSegment` 内部的 `ulChildID` 字段提取子轨道：

```text
.//field[@name='ulChildID']
```

常见树形位置：

```text
CAkMusicSegment
└── MusicSegmentInitialValues
    ├── ulNumChilds
    └── ulChildID
```

#### 4.7 音乐轨道 (MusicTrack)
```
MusicTrack (HIRCType.MUSIC_TRACK = 11)
├── object_id: 90001
└── file_ids: [12345, 67890]
```

说明：

- `MusicTrack.file_ids` 直接对应最终音频资源 ID。
- 也就是说，拿到这里的 `file_ids` 后，就已经完成了“事件 -> 资源 ID”的核心映射。
- `WwiserHIRC` 当前从下面这个 XML 位置提取最终资源 ID：

```text
.//list[@name='pPlaylist']//field[@name='sourceID']
```

对应树形位置：

```text
CAkMusicTrack
└── MusicTrackInitialValues
    └── pPlaylist
        └── sourceID
```

这里拿到的 `sourceID` 就是最终资源 ID，也就是：

```text
sourceID == <sourceID>.wem
```

#### 4.8 一个真实的音乐容器链路示意
```
Event
  -> Action.id_ext
  -> MusicSwitchContainer
  -> MusicRandomContainer
  -> MusicSegment
  -> MusicTrack
  -> source_id / file_id
```

以 `MUS_Map11Arcade_events.bnk` 中的 `Play_mus_map11_phase_select_Arcade` 为例，当前链路可以展开为：

```text
Event(3756353764)
  -> Action(392790484)
  -> ActionInitialValues.idExt = 563335300
  -> CAkMusicSwitchCntr(563335300)
  -> MusicSwitchCntrInitialValues.pNodes.audioNodeId
  -> [200855215, 104162796, 393516968, ...]
  -> CAkMusicRanSeqCntr
  -> MusicRanSeqCntrInitialValues.pPlayList.SegmentID
  -> [20394713, 298975373, 1053123264, 20118329, 186338091, 241377191, ...]
  -> CAkMusicSegment
  -> MusicSegmentInitialValues.ulChildID
  -> [649358229, 436372912, 80968655, 958641661, 584273829, 664628860, 595731544, 129417819]
  -> CAkMusicTrack
  -> MusicTrackInitialValues.pPlaylist.sourceID
  -> [293396007, 434740873, 403862142, 549272032, 228073295, 128820562, 689724454, 801502607]
```

这条链也说明了当前“新支持的音乐容器”是怎么找到资源 ID 的：

1. `Action.idExt` 先进入音乐容器入口。
2. `MusicSwitch` / `MusicRandom` / `MusicSegment` 负责继续提供可遍历的下游对象 ID。
3. 真正落到最终资源 ID 的位置是 `MusicTrackInitialValues.pPlaylist.sourceID`。

### 5. 最终映射结果

```
"Play_vo_Aurora_Move1" → [12345, 67890, 24680]
```

## 架构设计

### 核心类设计

#### 1. AudioMapping 数据类
```python
@dataclass
class AudioMapping:
    forward_mapping: Dict[str, List[int]]  # {事件名称: [音频文件ID列表]}
    reverse_mapping: Dict[int, List[str]]  # {音频文件ID: [事件名称列表]}
```

**职责**：
- 存储双向映射数据
- 提供O(1)复杂度的查询接口
- 支持映射合并和统计功能

#### 2. AudioEventMapper 映射器
```python
class AudioEventMapper:
    def __init__(self, events_input: Union[BIN, List[str]], hirc)
    def build_mapping(self) -> AudioMapping
```

**职责**：
- 从事件输入源构建映射关系
- 支持灵活输入（BIN文件或字符串列表）
- 使用BFS算法遍历容器层级

#### 3. MappingAnalyzer 分析器
```python
class MappingAnalyzer:
    def __init__(self, mapping: AudioMapping)
    def analyze_file_coverage(self, actual_files: List[str]) -> Dict
    def analyze_event_complexity(self) -> Dict
    def analyze_sound_reuse(self) -> Dict
```

**职责**：
- 对映射数据进行各种分析
- 返回分析结果字典
- 不涉及数据构建和IO操作

## 映射算法

### BFS遍历算法
使用广度优先搜索（BFS）遍历容器层级：

```python
1. 从Event的所有Action开始
2. 对每个Action获取目标对象ID
3. 检查目标对象类型：
   - Sound: 添加source_id到结果
   - MusicTrack: 添加file_ids到结果
   - Container: 将所有子对象加入队列
4. 重复直到队列为空
```

### 时间复杂度
- **构建阶段**: O(n × k)，n为事件数量，k为平均容器深度
- **查询阶段**: O(1)，双向映射提供常数时间查询
- 相比嵌套循环的O(n³)大幅提升性能

## 映射关系表

| 层级 | 对象类型 | HIRC类型 | 作用 | 包含内容 |
|------|----------|----------|------|----------|
| 1 | **Event** | 4 | 事件入口 | event_ids: Action ID列表 |
| 2 | **Action** | 3 | 动作定义 | id_ext: 目标对象ID |
| 3 | **Container** | 5,6 | 普通容器组织 | child_ids: 子对象ID列表 |
| 4 | **MusicSwitchContainer** | 12 | 音乐切换入口 | child_ids: 音乐子节点ID |
| 5 | **MusicRandom / Playlist** | 13 | 音乐随机或播放列表容器 | child_ids: Segment ID列表 |
| 6 | **MusicSegment** | 10 | 音乐段 | child_ids: Track ID列表 |
| 7 | **MusicTrack** | 11 | 音乐轨道 | file_ids: 最终资源ID列表 |
| 8 | **Sound** | 2 | 普通音频对象 | source_id: 最终音频文件ID |

## 特殊情况处理

### 1. 嵌套容器
```
Event → Action → SwitchContainer → RandomContainer → Sound
```

### 2. 音乐容器链
```
Event → Action → MusicSwitchContainer → MusicRandomContainer → MusicSegment → MusicTrack
```

### 3. 多路径映射
一个事件可能触发多个音频文件：
```
"Play_vo_Aurora_Attack" → [12345, 67890, 24680]
```

### 4. 空映射
某些事件可能没有关联音频：
```
"Play_UI_Click" → []  # 可能是UI音效，不在当前BNK中
```

## 覆盖率分析

### 文件分类
- **已分类文件**: 被至少一个事件引用的音频文件
- **未分类文件**: 存在于文件系统但未被任何事件引用
- **映射错误**: 被事件引用但实际不存在的文件

### 未分类文件可能原因
1. **背景音乐**: 直接通过代码调用，不通过事件系统
2. **环境音效**: 持续播放的环境声音
3. **动态音效**: 根据游戏状态动态生成的音效
4. **动作不是播放链**: 例如 Stop / State / Switch 控制类动作
5. **容器结构已解析但无可落地资源**: 例如只拿到控制节点，没有继续到 `MusicTrack`

## 使用示例

### 方式1: 默认推荐，使用 NativeHIRC
```python
from league_tools import BIN, NativeHIRC, AudioEventMapper, MappingAnalyzer

# 加载文件
bin_file = BIN('skin0.bin')
hirc = NativeHIRC.from_bnk('events.bnk')

# 创建映射器并构建映射
mapper = AudioEventMapper(bin_file, hirc)
mapping = mapper.build_mapping()

# 使用映射进行查询
events = mapping.find_events_by_sound_id(123456)
sounds = mapping.find_sounds_by_event_name("Play_vo_Aurora_Move1")

print(f"音频文件 123456 属于事件: {events}")
print(f"事件 Play_vo_Aurora_Move1 包含音频: {sounds}")
```

### 方式2: 使用事件名称列表（更灵活）
```python
# 只处理特定的事件
vo_events = [
    "Play_vo_Annie_Move1",
    "Play_vo_Annie_Attack1",
    "Play_vo_Annie_Death"
]

# 直接使用事件名称列表
mapper = AudioEventMapper(vo_events, hirc)
mapping = mapper.build_mapping()

print(f"成功处理了 {len(mapping.get_all_event_names())} 个事件")
```

### 方式3: 需要完整 XML/HIRC 结构时使用 WwiserHIRC
```python
from league_tools import BIN, WwiserHIRC, AudioEventMapper
from league_tools.utils.wwiser import WwiserManager

bin_file = BIN('skin0.bin')
wm = WwiserManager()
hirc = WwiserHIRC.from_bnk('events.bnk', wwiser_manager=wm)
mapping = AudioEventMapper(bin_file, hirc).build_mapping()
```

### 合并多个映射（处理多category）
```python
# 处理VO事件
vo_events = ["Play_vo_Annie_Move1", "Play_vo_Annie_Attack1"]
hirc_vo = NativeHIRC.from_bnk('annie_base_vo_events.bnk')
mapper_vo = AudioEventMapper(vo_events, hirc_vo)
mapping_vo = mapper_vo.build_mapping()

# 处理SFX事件
sfx_events = ["Play_sfx_Annie_Q", "Play_sfx_Annie_W"]
hirc_sfx = NativeHIRC.from_bnk('annie_base_sfx_events.bnk')
mapper_sfx = AudioEventMapper(sfx_events, hirc_sfx)
mapping_sfx = mapper_sfx.build_mapping()

# 合并映射
combined_mapping = mapping_vo.merge_with(mapping_sfx)
```

### 数据分析
```python
# 创建分析器
analyzer = MappingAnalyzer(combined_mapping)

# 文件覆盖率分析
actual_files = ['123456', '789012', '345678', '246810']
coverage = analyzer.analyze_file_coverage(actual_files)
print(f"覆盖率: {coverage['coverage_rate']:.1f}%")
print(f"未分类文件: {len(coverage['uncategorized_files'])} 个")

# 事件复杂度分析
complexity = analyzer.analyze_event_complexity()
print(f"简单事件: {complexity['simple_events']} 个")
print(f"复杂事件: {complexity['complex_events']} 个")

# 音频重用分析
reuse = analyzer.analyze_sound_reuse()
print(f"独占音频: {reuse['unique_sounds']} 个")
print(f"共享音频: {reuse['reused_sounds']} 个")

# 综合分析报告
analysis = analyzer.get_comprehensive_analysis(actual_files)
```

### 高级用法：批量查询
```python
# 批量查找多个音频文件对应的事件
sound_ids = [123456, 789012, 345678]
events_batch = mapping.find_events_by_sound_ids(sound_ids)

# 批量查找多个事件对应的音频文件
event_names = ["Play_vo_Annie_Move1", "Play_vo_Annie_Attack1"]
sounds_batch = mapping.find_sounds_by_event_names(event_names)

# 获取统计信息
stats = mapping.stats
print(f"总事件数: {stats['total_events']}")
print(f"总音频数: {stats['total_sounds']}")
print(f"平均每事件音频数: {stats['avg_sounds_per_event']}")
```

## 新版本特性

### 🎯 灵活输入支持
- **BIN文件模式**: 自动遍历 `data → bank_units → events` 提取所有事件
- **字符串数组模式**: 直接传入事件名称列表，自动计算项目当前事件哈希
- **向后兼容**: 现有代码无需修改

### 🔄 映射合并功能
- **merge_with()**: 合并多个AudioMapping实例
- **自动去重**: 相同事件的音频ID自动合并去重
- **多category支持**: 轻松处理VO、SFX等不同类别

### 📊 强大的分析功能
- **文件覆盖率**: 分析映射覆盖率和未分类文件
- **事件复杂度**: 统计简单事件vs复杂事件
- **音频重用**: 分析音频文件的重用情况
- **综合报告**: 一次性获取完整分析结果

### ⚡ 性能优势
- **双向映射**: 正向和反向查询都是O(1)复杂度
- **批量查询**: 支持批量处理多个查询请求
- **高效索引**: 一次性构建对象索引，避免重复查找
- **BFS遍历**: 避免递归调用，处理复杂嵌套结构
- **内存友好**: 使用集合和队列，空间复杂度O(n)
- **容错性强**: 单个事件错误不影响整体处理

## 相关文档

- [BNK 解析](formats_bnk.md)
- [音频 Bank 事件解释（开发）](audio_bank_parsing.md)

## API 设计原则

### 🏗️ 单一职责原则
- **AudioMapping**: 专注数据存储和查询
- **AudioEventMapper**: 专注映射构建逻辑
- **MappingAnalyzer**: 专注数据分析功能

### 🔧 灵活性设计
- **Union类型**: 支持多种输入类型
- **Builder模式**: AudioEventMapper作为构建器
- **数据类**: AudioMapping提供结构化数据存储

### 📈 可扩展性
- **接口一致**: 统一的查询和分析接口
- **模块化**: 各组件职责清晰，易于扩展
- **类型安全**: 完整的类型提示支持

## AudioMapping 方法详解

### 查询方法
```python
# 单项查询
events = mapping.find_events_by_sound_id(123456)
sounds = mapping.find_sounds_by_event_name("Play_vo_Annie_Move1")

# 批量查询
events_batch = mapping.find_events_by_sound_ids([123456, 789012])
sounds_batch = mapping.find_sounds_by_event_names(["Event1", "Event2"])

# 存在性检查
has_sound = mapping.has_sound_id(123456)
has_event = mapping.has_event_name("Play_vo_Annie_Move1")

# 获取所有ID
all_sounds = mapping.get_all_sound_ids()     # Set[int]
all_events = mapping.get_all_event_names()  # Set[str]
```

### 统计方法
```python
# 基础统计
stats = mapping.stats
# 返回: {
#     "total_events": 150,
#     "total_sounds": 230,
#     "total_mappings": 300,
#     "avg_sounds_per_event": 2.0,
#     "avg_events_per_sound": 1.3
# }

# 音频使用统计
usage_stats = mapping.get_sound_usage_stats()
# 返回: {
#     "max_usage": 5,        # 最多被5个事件使用
#     "min_usage": 1,        # 最少被1个事件使用
#     "avg_usage": 1.8,      # 平均被1.8个事件使用
#     "single_use_count": 180 # 180个音频只被1个事件使用
# }
```

### 数据操作方法
```python
# 转换为字典
data_dict = mapping.to_dict()

# 合并映射
combined = mapping1.merge_with(mapping2)
```

## MappingAnalyzer 分析详解

### 文件覆盖率分析
```python
actual_files = ['123456', '789012', '345678', '246810']
coverage = analyzer.analyze_file_coverage(actual_files)

# 返回结果:
{
    "total_files": 4,           # 总文件数
    "categorized_count": 3,     # 已分类文件数
    "uncategorized_count": 1,   # 未分类文件数
    "coverage_rate": 75.0,      # 覆盖率百分比
    "uncategorized_files": [246810],      # 未分类文件列表
    "mapping_not_exist": [],              # 映射中存在但实际不存在的文件
    "categorized_files": [123456, 789012, 345678]  # 已分类文件列表
}
```

### 事件复杂度分析
```python
complexity = analyzer.analyze_event_complexity()

# 返回结果:
{
    "total_events": 150,        # 总事件数
    "simple_events": 120,       # 简单事件数（包含1个音频文件）
    "complex_events": 30,       # 复杂事件数（包含多个音频文件）
    "avg_sounds_per_event": 2.0, # 平均每事件音频数
    "max_sounds_per_event": 8,   # 最多音频数的事件
    "min_sounds_per_event": 1    # 最少音频数的事件
}
```

### 音频重用分析
```python
reuse = analyzer.analyze_sound_reuse()

# 返回结果:
{
    "total_sounds": 230,        # 总音频数
    "unique_sounds": 180,       # 独占音频数（只被1个事件使用）
    "reused_sounds": 50,        # 重用音频数（被多个事件使用）
    "avg_events_per_sound": 1.3, # 平均每音频被多少事件使用
    "max_events_per_sound": 5,   # 最多被5个事件使用
    "min_events_per_sound": 1    # 最少被1个事件使用
}
```

## 局限性与改进方向

### 当前局限性
1. **容器类型**: 目前支持Event、Action、Sound、RandomContainer、SwitchContainer
2. **复杂状态**: 不处理复杂的状态机和切换逻辑
3. **音乐系统**: 暂不支持MusicSegment、MusicTrack等音乐相关容器

### 未来扩展方向
1. **音乐容器支持**: 添加对MusicSegment、MusicTrack的支持
2. **状态机处理**: 处理复杂的Switch和State逻辑
3. **缓存优化**: 添加映射结果缓存机制
4. **可视化工具**: 生成映射关系的图形化表示
5. **增量更新**: 支持动态更新映射关系
6. **并行处理**: 利用多核CPU并行构建映射

## 快速参考

### 创建映射
```python
# 方式1: BIN文件
mapper = AudioEventMapper(bin_file, hirc)

# 方式2: 事件名称列表
mapper = AudioEventMapper(["Event1", "Event2"], hirc)

# 构建映射
mapping = mapper.build_mapping()
```

### 查询操作
```python
# 查询音频对应的事件
events = mapping.find_events_by_sound_id(123456)

# 查询事件对应的音频
sounds = mapping.find_sounds_by_event_name("Play_vo_Annie_Move1")

# 获取统计信息
stats = mapping.stats
```

### 分析操作
```python
# 创建分析器
analyzer = MappingAnalyzer(mapping)

# 各种分析
coverage = analyzer.analyze_file_coverage(actual_files)
complexity = analyzer.analyze_event_complexity()
reuse = analyzer.analyze_sound_reuse()
comprehensive = analyzer.get_comprehensive_analysis(actual_files)
```

### 映射合并
```python
# 合并多个映射
combined = mapping1.merge_with(mapping2).merge_with(mapping3)
```
