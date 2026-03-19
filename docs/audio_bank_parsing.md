# 音频 Bank 事件映射实现说明（开发文档）

本文档是开发向解释文档，用来说明音频事件是如何从 `BIN / events.bnk / audio.bnk|wpk` 这几类文件之间串起来的。

- 偏工程落地与调用入口，请看 [audio_mapping.md](audio_mapping.md)
- 偏二进制结构与字段顺序，请看本文

本文档只讨论文件之间的解析逻辑，不讨论任何特定项目中的 UI、类设计或调用链。目标是说明如何从一组 Riot / Wwise 相关文件中，还原出：

```text
事件名 -> 一个或多个 WEM 文件 ID -> 对应音频字节
```

文档面向“要用其他语言自行实现解析器”的场景，因此重点是：

1. 输入文件分别提供什么信息
2. 这些信息之间如何建立关联
3. 二进制结构如何读取
4. 如何把事件名最终解析到实际音频数据

## 1. 问题定义

给定一组互相关联的文件：

- `xxx_audio.wpk` 或 `xxx_audio.bnk`
- `xxx_events.bnk`
- 对应 WAD 中的 `.bin`

需要得到如下结果：

```text
Play_vo_Aatrox_AatroxE_cast3D
  -> [822202460, 780614653]
  -> 822202460.wem 的字节
  -> 780614653.wem 的字节
```

关键事实是：

- `WPK` / `audio BNK` 里通常只有 `wemId`
- 事件名字符串通常不在 `WPK` 里
- 事件名来自 `.bin`
- 事件到 `wemId` 的关系来自 `_events.bnk` 的 HIRC 图

因此需要把三类文件组合起来解析。

## 2. 输入文件各自的职责

### 2.1 `.bin`

职责：

- 提供事件名字符串
- 通过固定 hash 算法把事件名映射为 32-bit `eventId`

输出：

```text
eventId -> eventName
```

### 2.2 `_events.bnk`

职责：

- 提供 HIRC 对象图
- 提供 `Event` 对象
- 提供 `Event -> Action -> Container / Sound / MusicTrack` 的连接关系

输出：

```text
eventId -> wemId[]
```

或者更准确地说：

```text
eventId -> HIRC graph traversal -> wemId[]
```

### 2.3 `_audio.wpk`

职责：

- 提供 `wemId -> offset,size`
- 允许按 `wemId` 在 WPK 容器中找到真正的音频字节

输出：

```text
wemId -> (offset, size)
```

### 2.4 `_audio.bnk`

职责：

- 在没有 WPK 时，自己承担音频容器角色
- 通过 `DIDX + DATA` 提供 `wemId -> absoluteOffset,size`

输出：

```text
wemId -> (absoluteOffset, size)
```

## 3. 整体映射链

整个过程可以抽象为 4 步：

```text
1. 从 .bin 提取事件名
2. 把事件名 hash 成 eventId
3. 从 _events.bnk 的 HIRC 图里，把 eventId 解析到一个或多个 wemId
4. 从 _audio.wpk 或 _audio.bnk 中，把 wemId 解析到音频字节
```

写成更完整的链路：

```text
eventName
  -> hash(eventName)
  -> eventId
  -> HIRC Event object
  -> Action / Container / Sound / MusicTrack
  -> wemId[]
  -> WPK entry or DIDX entry
  -> offset,size
  -> audio bytes
```

## 4. `.bin` 中的事件名提取

`.bin` 的处理目标不是完整解析整个文件，而是提取出“用于音频事件命名的字符串”。

### 4.1 需要扫描的两类容器

实践上需要扫描两类 magic 片段：

1. `events` 容器
   - magic：`84 E3 D8 12 80 10`

2. `music` 容器
   - magic：`D4 4F 9C 9F 83`

这两个容器都可能包含事件名字符串。

### 4.2 `events` 容器的读取方式

从 magic 起点往后，按如下布局读取：

```text
[6 bytes]  magic = 84 E3 D8 12 80 10
[4 bytes]  objectSize，跳过
[4 bytes]  amount，uint32，小端

循环 amount 次：
  [2 bytes]  stringLength，uint16，小端
  [N bytes]  ASCII 字符串
```

可以抽象为：

```text
events_block := magic + objectSize + amount + repeated(length + bytes)
```

### 4.3 `music` 容器的读取方式

从 magic 起点往后，按如下布局读取：

```text
[5 bytes]  magic = D4 4F 9C 9F 83
[4 bytes]  typeHash，uint32
[4 bytes]  objectSize，跳过
[2 bytes]  amount，uint16

循环 amount 次：
  [4 bytes]  nameHash，跳过
  [1 byte ]  binType，预期为 0x10，表示 string
  [2 bytes]  stringLength，uint16
  [N bytes]  ASCII 字符串
```

如果 `binType != 0x10`，通常应当认为当前块格式不符合预期，至少这一段不再继续按字符串解释。

### 4.4 输出结果

从 `.bin` 提取出来的不是“事件对象”，而是一个映射表：

```text
eventId -> eventName
```

其中 `eventId` 是对字符串执行固定 hash 算法得到的 32-bit 值。

## 5. 事件名哈希算法

事件名需要转成与 `_events.bnk` 中 `Event.Id` 可匹配的值。常见可用实现如下：

```text
offsetBasis = 2166136261
prime = 16777619

hash = offsetBasis
for each ASCII char c in string:
    if 'A' <= c <= 'Z':
        c = c + 32
    hash = hash * prime
    hash = hash XOR c
return hash as uint32
```

要点：

1. 这是 FNV1 风格，不是 FNV1a
   - 顺序是“先乘再 XOR”

2. 需要做 ASCII 小写归一
   - 大写字母先转小写

3. 结果是 32-bit 无符号整数

因此：

```text
eventId = Hash(eventName)
```

后面会用它去匹配 BNK 的 `Event.Id`。

## 6. BNK 的顶层结构

BNK 文件可以视为多个 section 顺序拼接。每个 section 的统一头部是：

```text
[4 bytes]  signature，ASCII
[4 bytes]  sectionSize，uint32，小端
[sectionSize bytes] payload
```

常见 section：

1. `BKHD`
2. `HIRC`
3. `DIDX`
4. `DATA`

其他 section 可以先跳过，只要保留“跳到下一 section”能力即可。

## 7. `BKHD` 结构

如果只为构建事件映射，通常只需要取前两个字段：

```text
[4 bytes] Version
[4 bytes] Id
```

其中 `Version` 很重要，因为 HIRC 某些对象的局部布局会随版本切换。

## 8. `HIRC` 结构总览

`HIRC` 是整个事件到声音映射的核心。它可以理解为一个对象图容器。

### 8.1 HIRC section 头

`HIRC` payload 起始处先是：

```text
[4 bytes] objectCount，uint32
```

随后连续存放 `objectCount` 个对象。

### 8.2 每个 HIRC 对象的公共头

每个对象都以如下头部开头：

```text
[1 byte ] Type
[4 bytes] Size
[4 bytes] Id
[...    ] Payload
```

一个实用解释方式是：

- `Type`：对象类型
- `Size`：从 `Id` 开始到对象 payload 结束的总长度
- `Id`：对象自己的唯一标识

因此对象结束位置可按以下方式计算：

```text
objEnd = position_after_id + (Size - 4)
```

这里 `-4` 的原因是：

- 读取 `objEnd` 时，流位置已经在 `Id` 后面
- 而 `Size` 把 `Id` 自己的 4 字节也算进去了

### 8.3 建议的解析策略

为了实现稳健：

1. 先读取对象公共头
2. 针对已知 `Type` 按规则解析需要的字段
3. 无论是否完整理解 payload，最后都强制跳到 `objEnd`

这样即使某种对象只部分支持，也不会破坏后续对象读取。

## 9. 与事件映射相关的 HIRC 对象类型

如果目标只是还原“事件名 -> wemId”，核心对象类型只有这些：

1. `Event`
2. `Action`
3. `Sound`
4. `RandomOrSequenceContainer`
5. `SwitchContainer`
6. `MusicSegment`
7. `MusicPlaylistContainer`
8. `MusicSwitchContainer`
9. `MusicTrack`

可以把它们看成这样一张图：

```text
Event
  -> Action
    -> Container
      -> Container
        -> Sound
        -> MusicTrack
```

终点通常有两种：

1. `Sound.WemId`
2. `MusicTrack` 里的 `fileId`

## 10. `Event` 对象结构

用途：

- 以 `Event.Id` 作为事件对象的唯一标识
- 保存它要触发的 `ActionIds`

布局：

```text
Header:
  [1 ] Type = Event
  [4 ] Size
  [4 ] Id

Payload:
  if BKHD.Version == 58:
    [4 ] actionCount，uint32
  else:
    [1 ] actionCount，uint8

  [4 * actionCount] ActionIds
```

输出：

```text
Event.Id -> ActionIds[]
```

## 11. `Action` 对象结构

用途：

- 把 `Event` 连接到下游对象

可按如下布局读取：

```text
Header:
  [1 ] Type = Action
  [4 ] Size
  [4 ] Id

Payload:
  [1 ] Scope
  [1 ] ActionType

  if ActionType == 25:
    [5 ] skipped
    [1 ] countA
    [5 * countA] skipped
    [1 ] countB
    [9 * countB] skipped
    [4 ] SwitchGroupId
    [4 ] SwitchId
  else:
    [4 ] ObjectId
```

对于“事件到声音映射”的主线场景，最重要的是：

```text
Action.ObjectId
```

通常遍历算法会从这里继续往下走。

注意：

- 某些特殊 `ActionType` 可能不适合只看 `ObjectId`
- 如果要追求完整兼容，后续还需要补充更多 action 语义

## 12. `Sound` 对象结构

用途：

- 直接给出一个 `wemId`

布局：

```text
Header:
  [1 ] Type = Sound
  [4 ] Size
  [4 ] Id

Payload:
  [4 ] skipped
  [1 ] StreamType
  [4 ] WemId
  [4 ] SourceId
  [4 ] skipped
  [4 ] ObjectId
```

核心字段：

- `WemId`

一旦解析到 `Sound`，通常就已经拿到音频文件标识，不必再沿着 `ObjectId` 继续追。

## 13. 容器类对象结构

容器类对象本身不直接给出 `wemId`，而是给出一组子对象 ID，需要递归遍历。

### 13.1 `RandomOrSequenceContainer`

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  BaseParams
  [24] skipped
  [4 ] childCount
  [4 * childCount] Children
```

### 13.2 `SwitchContainer`

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  BaseParams
  [1 ] GroupType
  if version <= 0x59:
    [3 ] skipped
  [4 ] GroupId
  [5 ] skipped
  [4 ] childCount
  [4 * childCount] Children
```

### 13.3 `MusicSegment`

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  [1 ] skipped
  BaseParams
  [4 ] count
  [4 * count] Children
```

### 13.4 `MusicPlaylistContainer`

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  [1 ] skipped
  BaseParams
  [4 ] count
  [4 * count] Children
```

### 13.5 `MusicSwitchContainer`

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  [1 ] skipped
  BaseParams
  [4 ] numSwitchChildren
  [4 * numSwitchChildren] Children
  [23] skipped
  [4 ] numStingers
  [24 * numStingers] skipped
  [4 ] numRules

  repeat numRules times:
    [4 ] numSources
    [4 * numSources] skipped
    [4 ] numDestinations
    [4 * numDestinations] skipped
    [45 or 47] skipped
    [1 ] hasTransObject
    if hasTransObject:
      [30] skipped
```

### 13.6 这些容器的共同输出

都可以抽象为：

```text
containerId -> childObjectIds[]
```

## 14. `MusicTrack` 对象结构

`MusicTrack` 非常重要，因为它的 children 不是“子 HIRC object id”，而是“文件 ID”。

布局：

```text
Header:
  [1 ] Type
  [4 ] Size
  [4 ] Id

Payload:
  [1 ] skipped
  [4 ] playlistItemCount
  [14 * playlistItemCount] skipped
  [4 ] sourcesCount

  repeat sourcesCount times:
    [4 ] trackIndex，跳过
    [4 ] fileId
    [36] skipped
```

关键语义：

```text
fileId == wemId
```

因此遍历时：

- 不要把 `MusicTrack.Children` 当成 HIRC 对象继续递归
- 要直接把它们当成 `wemId`

这是实现里最容易出错的一点。

## 15. `BaseParams` 的读取顺序

多种容器对象在 payload 里都包含一段“基础参数块”。即使不完全理解它的语义，也需要按正确顺序消耗字节，才能继续读到 `childCount`。

可以按下面的顺序处理：

### 15.1 `SkipFx`

```text
[1 ] skipped
[1 ] fxCount
if fxCount > 0:
  [1 + fxCount * (version <= 145 ? 7 : 6)] skipped

if version > 136:
  [1 ] skipped
  [1 ] fxCount
  [6 * fxCount] skipped

if 89 < version <= 145:
  [1 ] skipped
```

### 15.2 固定字段

```text
[4 ] busId
[4 ] parentId
[1 or 2] skipped，取决于 version <= 89
```

### 15.3 `InitParams`

```text
[1 ] countA
[5 * countA] skipped
[1 ] countB
[9 * countB] skipped
```

### 15.4 `PosParams`

```text
[1 ] posBits

if hasPos and has3d:
  [1 ] skipped

if hasAutomation:
  [5 ] skipped
  [4 ] count1
  [16 * count1] skipped
  [4 ] count2
  [20 * count2] skipped
```

### 15.5 `Aux`

```text
[1 ] flags
if hasAux:
  [16] skipped
if version > 135:
  [4 ] skipped
```

### 15.6 `StateGroups`

```text
[6 ] skipped
[1 ] countA
[3 * countA] skipped
[1 ] countB
repeat countB times:
  [5 ] skipped
  [1 ] innerCount
  [8 * innerCount] skipped
```

### 15.7 `Rtpc`

```text
[2 ] rtpcCount
repeat rtpcCount times:
  [13 or 12] skipped
  [2 ] pointCount
  [12 * pointCount] skipped
```

### 15.8 BaseParams 输出

即使你不关心所有细节，也建议至少保留：

- `parentId`
- `busId`

因为它们在某些更高级的图重建场景中仍然有用。

## 16. 事件到 `wemId` 的遍历算法

前面已经有：

1. `eventId -> eventName`
2. HIRC object dictionary：`objectId -> object`

接下来就要从 `Event` 对象递归求出 `wemId`。

建议算法如下。

### 16.1 构建对象字典

先把 HIRC 所有对象按 `Id` 建索引：

```text
objects[object.Id] = object
```

### 16.2 对每个 `Event` 开始遍历

```text
for each object in objects:
    if object.Type == Event:
        eventId = object.Id
        eventName = eventNameMap.get(eventId, str(eventId))
        for actionId in object.ActionIds:
            Traverse(actionId)
```

### 16.3 `Traverse(objectId)` 规则

```text
if objectId not in objects:
    return

obj = objects[objectId]

switch obj.Type:
  Sound:
      output obj.WemId

  Action:
      Traverse(obj.ObjectId)

  RandomOrSequenceContainer:
      for child in obj.Children:
          Traverse(child)

  SwitchContainer:
      for child in obj.Children:
          Traverse(child)

  MusicSegment:
      for child in obj.Children:
          Traverse(child)

  MusicPlaylistContainer:
      for child in obj.Children:
          Traverse(child)

  MusicSwitchContainer:
      for child in obj.Children:
          Traverse(child)

  MusicTrack:
      for fileId in obj.Children:
          output fileId as wemId
```

### 16.4 输出形式

最终你想得到：

```text
eventId -> wemId[]
```

再结合 `.bin` 的映射：

```text
eventName -> wemId[]
```

### 16.5 未命中的音频

如果某些 `wemId` 出现在 `_audio.wpk` / `_audio.bnk` 中，但没有被任何 `Event` 遍历命中，可以额外归类为：

```text
Unknown -> wemId[]
```

这不是格式要求，但对分析工具很实用。

## 17. WPK 结构

WPK 是一个以 `wemId` 为索引的独立容器。

### 17.1 文件头

```text
[4 bytes]  signature = "r3d2"
[4 bytes]  version
[4 bytes]  wemCount
[4 * wemCount bytes] entryOffsetTable
```

### 17.2 条目结构

对每个 `entryOffset`，跳过去按如下结构读取：

```text
[4 bytes]  dataOffset
[4 bytes]  dataSize
[4 bytes]  nameLengthInChars
[2 * nameLengthInChars bytes] UTF-16 文件名，例如 "822202460.wem"
```

### 17.3 `wemId` 的来源

`wemId` 不是单独字段，而是从 UTF-16 文件名里解析出来：

```text
"822202460.wem" -> wemId = 822202460
```

因此若文件名不符合：

```text
^\d+\.wem$
```

这一条目至少不能直接用于当前映射逻辑。

### 17.4 WPK 输出

解析完成后，可得到：

```text
wemId -> (offset, size)
```

后续提取字节时：

```text
audioBytes = wpkBytes[offset : offset + size]
```

## 18. `_audio.bnk` 的 `DIDX + DATA`

如果没有 WPK，而音频数据在 `_audio.bnk` 中，那么依赖：

- `DIDX`
- `DATA`

### 18.1 `DIDX` 结构

可以按每 12 字节一个条目解释：

```text
[4 bytes] wemId
[4 bytes] offset
[4 bytes] size
```

### 18.2 `DATA` 结构

`DATA` section 的 payload 就是原始音频字节区。  
为了解析 `DIDX.offset`，只需要记录：

```text
dataSectionPayloadAbsoluteStart
```

### 18.3 绝对偏移计算

`DIDX` 中的 `offset` 是相对 `DATA` payload 起点的偏移，因此：

```text
absoluteOffset = dataSectionPayloadAbsoluteStart + didxOffset
```

### 18.4 输出

最终可得到：

```text
wemId -> (absoluteOffset, size)
```

后续取字节：

```text
audioBytes = bnkBytes[absoluteOffset : absoluteOffset + size]
```

## 19. 一个推荐的数据模型

为了便于跨语言实现，建议把解析结果拆成几张中间表，而不是强耦合成对象树。

### 19.1 事件名表

```text
eventNameMap: Dict<uint32, string>
```

### 19.2 HIRC 对象表

```text
hircObjects: Dict<uint32, HircObject>
```

其中 `HircObject` 只需要保留和遍历相关的信息：

```text
type
id
actionIds?[]
objectId?
children?[]
wemId?
```

### 19.3 音频索引表

```text
wemIndex: Dict<uint32, AudioLocation>
```

其中 `AudioLocation` 至少包含：

```text
containerType = WPK | BNK
offset
size
```

### 19.4 最终输出表

```text
resolvedEvents: Dict<string, List<uint32>>
```

或者如果你想保留更多信息：

```text
resolvedEvents: Dict<string, List<AudioRef>>

AudioRef:
  wemId
  containerType
  offset
  size
```

## 20. 一个推荐的实现顺序

如果要从零实现，建议按下面顺序拆模块。

### 20.1 模块 1：哈希函数

先实现：

```text
HashEventName(string) -> uint32
```

并拿几个已知样本做回归。

### 20.2 模块 2：`.bin` 字符串提取

实现：

```text
ExtractEventNames(binBytes) -> Dict<uint32, string>
```

注意：

- 不需要完整理解 BIN
- 只要稳定扫出 events/music 字符串并哈希即可

### 20.3 模块 3：BNK section 扫描器

实现：

```text
ParseSections(bnkBytes) -> BKHD, HIRC, DIDX, DATA
```

### 20.4 模块 4：HIRC 对象解析器

实现：

```text
ParseHircObjects(hircBytes, version) -> Dict<uint32, HircObject>
```

### 20.5 模块 5：WPK 或 DIDX 音频索引

实现二选一或都实现：

```text
ParseWpkIndex(wpkBytes) -> Dict<uint32, AudioLocation>
ParseAudioBnkIndex(audioBnkBytes) -> Dict<uint32, AudioLocation>
```

### 20.6 模块 6：图遍历器

实现：

```text
ResolveEventToWems(hircObjects, eventNameMap) -> Dict<string, List<uint32>>
```

### 20.7 模块 7：字节提取器

实现：

```text
ReadAudioBytes(containerBytes, location) -> byte[]
```

## 21. 伪代码

下面给出一套简化伪代码。

### 21.1 主流程

```text
eventNameMap = ExtractEventNames(binBytes)
eventsBnk = ParseBnk(eventsBnkBytes)

if hasWpk:
    wemIndex = ParseWpkIndex(audioWpkBytes)
else:
    wemIndex = ParseAudioBnkIndex(audioBnkBytes)

hircObjects = eventsBnk.hircObjects

resolved = {}

for each obj in hircObjects.values():
    if obj.type != Event:
        continue

    eventId = obj.id
    eventName = eventNameMap.get(eventId, str(eventId))

    wemIds = OrderedSet()
    for actionId in obj.actionIds:
        Traverse(actionId, hircObjects, wemIds)

    resolved[eventName] = list(wemIds)
```

### 21.2 遍历函数

```text
function Traverse(objectId, hircObjects, outputWemIds):
    obj = hircObjects.get(objectId)
    if obj is null:
        return

    switch obj.type:
        case Sound:
            outputWemIds.add(obj.wemId)
            return

        case Action:
            Traverse(obj.objectId, hircObjects, outputWemIds)
            return

        case RandomOrSequenceContainer:
        case SwitchContainer:
        case MusicSegment:
        case MusicPlaylistContainer:
        case MusicSwitchContainer:
            for childId in obj.children:
                Traverse(childId, hircObjects, outputWemIds)
            return

        case MusicTrack:
            for fileId in obj.children:
                outputWemIds.add(fileId)
            return

        default:
            return
```

### 21.3 音频字节读取

```text
for each eventName, wemIds in resolved:
    for wemId in wemIds:
        loc = wemIndex[wemId]
        audioBytes = containerBytes[loc.offset : loc.offset + loc.size]
```

## 22. 易错点

### 22.1 把 `MusicTrack.Children` 误当成 HIRC object id

这是最常见错误。正确理解是：

```text
MusicTrack.Children == fileId == wemId
```

### 22.2 忘记对事件名做小写归一

如果 hash 时不把 `A-Z` 转小写，通常无法匹配到 `Event.Id`。

### 22.3 把 `DIDX.offset` 当成文件绝对偏移

在 `_audio.bnk` 中，`DIDX.offset` 是相对 `DATA payload` 起点的偏移，不是相对整个 BNK 文件开头。

### 22.4 没有强制跳到 `objEnd`

如果某个对象只读了一部分字段，必须强制跳到对象末尾，否则后面的 HIRC 对象会错位。

### 22.5 过度依赖完整格式文档

如果你的目标只是恢复“事件名 -> wemId”，完全没必要一次性实现完整 Wwise 规范。  
最有效的策略是：

1. 把事件图相关对象先吃透
2. 先建立正确的 `eventId -> wemId` 图
3. 再补其他对象语义

## 23. 最终结论

如果只从文件关系角度理解，这套机制本质上就是：

```text
.bin
  提供 eventName

Hash(eventName)
  得到 eventId

_events.bnk / HIRC
  提供 eventId 如何沿对象图走到 wemId

_audio.wpk 或 _audio.bnk
  提供 wemId 对应的真实音频数据位置
```

因此，事件名到音频文件 ID 的精确关系是：

```text
eventName
  -> eventId
  -> Event object
  -> graph traversal
  -> wemId[]
  -> audio bytes
```

这就是脱离任何特定项目代码之后，仍然成立的最小实现模型。
