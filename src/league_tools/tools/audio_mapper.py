# 🐍 Simple is better than complex.
# 🐼 简单优于复杂
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: Cursor
# @Create  : 2025/1/20 12:00
# @Update  : 2025/8/4 13:42
# @Detail  : 音频事件映射工具


"""
音频事件映射工具

提供从BIN文件的事件字符串到BNK文件中音频ID的高级映射功能。
基于底层解析器构建的应用层工具。
"""

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Protocol, Set, Union

from ..formats import BIN
from ..utils.hash import str_fnv_32


class HIRCBankLike(Protocol):
    """AudioEventMapper 依赖的最小 bank 接口。"""

    events: Mapping[int, object]
    event_actions: Mapping[int, object]
    sounds: Mapping[int, object]
    random_containers: Mapping[int, object]
    switch_containers: Mapping[int, object]
    music_segments: Mapping[int, object]
    music_playlist_containers: Mapping[int, object]
    music_switch_containers: Mapping[int, object]
    music_tracks: Mapping[int, object]


class HIRCLike(Protocol):
    """AudioEventMapper 依赖的最小 HIRC 接口。"""

    banks: Mapping[str, HIRCBankLike]


@dataclass
class AudioMapping:
    """
    音频事件映射数据类

    负责存储双向映射数据并提供高效查询接口。
    将数据存储和查询逻辑分离，提供O(1)复杂度的反向查询能力。

    Attributes:
        forward_mapping: 正向映射 {事件名称: [音频文件ID列表]}
        reverse_mapping: 反向映射 {音频文件ID: [事件名称列表]}
    """

    forward_mapping: Dict[str, List[int]]  # {event_name: [sound_ids]}
    reverse_mapping: Dict[int, List[str]]  # {sound_id: [event_names]}

    def __post_init__(self):
        """
        初始化后处理：确保数据排序和构建反向映射

        对传入的正向映射数据进行排序，确保数据一致性。
        """
        # 对正向映射的值进行排序，确保数据一致性
        for event_name in self.forward_mapping:
            self.forward_mapping[event_name] = sorted(self.forward_mapping[event_name])

        # 如果反向映射为空，则自动构建
        if not self.reverse_mapping and self.forward_mapping:
            self.reverse_mapping = self._build_reverse_mapping(self.forward_mapping)

    @staticmethod
    def _build_reverse_mapping(forward: Dict[str, List[int]]) -> Dict[int, List[str]]:
        """
        从正向映射构建反向映射

        确保生成的反向映射中的事件名称列表是排序的，以保证数据一致性。

        :param forward: 正向映射字典
        :return: 反向映射字典
        """
        reverse = {}
        for event_name, sound_ids in forward.items():
            for sound_id in sound_ids:
                if sound_id not in reverse:
                    reverse[sound_id] = []
                reverse[sound_id].append(event_name)

        # 对每个音频ID对应的事件名称列表进行排序，确保数据一致性
        for sound_id in reverse:
            reverse[sound_id].sort()

        return reverse

    # ========================= 查询方法 =========================

    def find_events_by_sound_id(self, sound_id: int) -> List[str]:
        """
        根据音频文件ID查找对应的事件名称列表

        返回的事件名称列表已排序，确保结果一致性。

        :param sound_id: 音频文件ID
        :return: 包含该音频文件的事件名称列表（已排序）
        """
        return sorted(self.reverse_mapping.get(sound_id, []))

    def find_sounds_by_event_name(self, event_name: str) -> List[int]:
        """
        根据事件名称查找对应的音频文件ID列表

        返回的音频文件ID列表已排序，确保结果一致性。

        :param event_name: 事件名称
        :return: 该事件包含的音频文件ID列表（已排序）
        """
        return sorted(self.forward_mapping.get(event_name, []))

    def has_sound_id(self, sound_id: int) -> bool:
        """
        检查音频文件ID是否存在于映射中

        :param sound_id: 音频文件ID
        :return: 是否存在
        """
        return sound_id in self.reverse_mapping

    def has_event_name(self, event_name: str) -> bool:
        """
        检查事件名称是否存在于映射中

        :param event_name: 事件名称
        :return: 是否存在
        """
        return event_name in self.forward_mapping

    def get_all_sound_ids(self) -> Set[int]:
        """获取所有音频文件ID集合"""
        return set(self.reverse_mapping.keys())

    def get_all_event_names(self) -> Set[str]:
        """获取所有事件名称集合"""
        return set(self.forward_mapping.keys())

    def find_events_by_sound_ids(self, sound_ids: List[int]) -> Dict[int, List[str]]:
        """
        批量查找多个音频文件ID对应的事件

        返回的结果字典按音频文件ID排序，每个事件名称列表也已排序。

        :param sound_ids: 音频文件ID列表
        :return: {音频文件ID: [事件名称列表]}（结果已排序）
        """
        # 按音频文件ID排序处理，确保结果一致性
        return {
            sound_id: self.find_events_by_sound_id(sound_id)
            for sound_id in sorted(sound_ids)
        }

    def find_sounds_by_event_names(
        self, event_names: List[str]
    ) -> Dict[str, List[int]]:
        """
        批量查找多个事件名称对应的音频文件

        返回的结果字典按事件名称排序，每个音频文件ID列表也已排序。

        :param event_names: 事件名称列表
        :return: {事件名称: [音频文件ID列表]}（结果已排序）
        """
        # 按事件名称排序处理，确保结果一致性
        return {
            event_name: self.find_sounds_by_event_name(event_name)
            for event_name in sorted(event_names)
        }

    # ========================= 统计方法 =========================

    @property
    def stats(self) -> Dict[str, any]:
        """
        获取映射统计信息

        :return: 统计信息字典
        """
        total_sounds = len(self.reverse_mapping)
        total_events = len(self.forward_mapping)
        total_mappings = sum(len(sounds) for sounds in self.forward_mapping.values())

        return {
            "total_events": total_events,
            "total_sounds": total_sounds,
            "total_mappings": total_mappings,
            "avg_sounds_per_event": round(total_mappings / max(total_events, 1), 2),
            "avg_events_per_sound": round(total_mappings / max(total_sounds, 1), 2),
        }

    def get_sound_usage_stats(self) -> Dict[str, any]:
        """
        获取音频文件使用情况统计

        :return: 使用情况统计字典
        """
        usage_counts = [len(events) for events in self.reverse_mapping.values()]
        if not usage_counts:
            return {
                "max_usage": 0,
                "min_usage": 0,
                "avg_usage": 0,
                "single_use_count": 0,
            }

        return {
            "max_usage": max(usage_counts),
            "min_usage": min(usage_counts),
            "avg_usage": round(sum(usage_counts) / len(usage_counts), 2),
            "single_use_count": sum(1 for count in usage_counts if count == 1),
        }

    def to_dict(self) -> Dict[str, any]:
        """
        转换为字典格式，便于序列化或传输

        输出的字典键按顺序排列，确保结果一致性。

        :return: 完整的映射数据字典（键已排序）
        """
        # 确保正向映射的键按字母顺序排列
        sorted_forward_mapping = {
            k: sorted(v) for k, v in sorted(self.forward_mapping.items())
        }

        # 确保反向映射的键按数字顺序排列
        sorted_reverse_mapping = {
            str(k): sorted(v) for k, v in sorted(self.reverse_mapping.items())
        }

        return {
            "forward_mapping": sorted_forward_mapping,
            "reverse_mapping": sorted_reverse_mapping,
            "stats": self.stats,
            "sound_usage_stats": self.get_sound_usage_stats(),
        }

    def merge_with(self, other: "AudioMapping") -> "AudioMapping":
        """
        与另一个AudioMapping合并

        合并后的数据会保持排序状态，确保结果一致性。

        :param other: 另一个AudioMapping实例
        :return: 合并后的新AudioMapping实例
        """
        # 合并正向映射
        merged_forward = self.forward_mapping.copy()
        for event_name, sound_ids in other.forward_mapping.items():
            if event_name in merged_forward:
                # 如果事件名称已存在，合并音频ID列表并去重、排序
                existing_ids = set(merged_forward[event_name])
                new_ids = set(sound_ids)
                merged_forward[event_name] = sorted(list(existing_ids | new_ids))
            else:
                # 确保新添加的音频ID列表也是排序的
                merged_forward[event_name] = sorted(sound_ids.copy())

        return AudioMapping(forward_mapping=merged_forward, reverse_mapping={})


class AudioEventMapper:
    """
    音频事件映射器

    职责：从事件输入源和 HIRC 兼容对象构建 AudioMapping 实例。
    支持两种灵活的输入方式：BIN文件或事件名称字符串列表。

    Example:
        >>> from league_tools import BIN, NativeHIRC
        >>> from league_tools.tools import AudioEventMapper, MappingAnalyzer
        >>>
        >>> hirc = NativeHIRC.from_bnk('events.bnk')
        >>>
        >>> # 方式1：使用BIN文件（向后兼容）
        >>> bin_file = BIN('skin0.bin')
        >>> mapper1 = AudioEventMapper(bin_file, hirc)
        >>> mapping1 = mapper1.build_mapping()
        >>>
        >>> # 方式2：使用字符串列表（更灵活）
        >>> event_names = ["Play_vo_Annie_Move1", "Play_vo_Annie_Attack1"]
        >>> mapper2 = AudioEventMapper(event_names, hirc)
        >>> mapping2 = mapper2.build_mapping()
        >>>
        >>> # 合并多个映射（处理多个category）
        >>> combined_mapping = mapping1.merge_with(mapping2)
        >>>
        >>> # 使用映射进行查询
        >>> events = combined_mapping.find_events_by_sound_id(123456)
        >>> sounds = combined_mapping.find_sounds_by_event_name("Play_vo_Annie_Move1")
        >>>
        >>> # 使用分析器进行分析
        >>> analyzer = MappingAnalyzer(combined_mapping)
        >>> coverage = analyzer.analyze_file_coverage(['123456', '789012'])
    """

    def __init__(self, events_input: Union[BIN, List[str]], hirc: HIRCLike):
        """
        初始化音频事件映射器

        :param events_input: 事件输入源，支持两种类型：
                            - BIN文件对象：从中提取StringHash
                            - 字符串列表：事件名称列表，会自动计算hash
        :param hirc: 已解析的 HIRC 对象，支持 wwiser/native 两种来源
        """
        self.events_input = events_input
        self.hirc = hirc
        self._object_index = None  # 对象索引缓存

    def build_mapping(self) -> AudioMapping:
        """
        构建音频事件映射

        生成的映射数据会按键排序，确保每次执行结果一致。

        :return: AudioMapping实例，包含完整的双向映射数据
        """
        # 提取所有事件字符串
        string_list = self._extract_event_strings()

        # 构建统一索引
        if self._object_index is None:
            self._object_index = self._build_unified_index()

        # 构建正向映射
        forward_mapping = {}

        # 按事件名称排序处理，确保结果一致性
        sorted_string_list = sorted(string_list, key=lambda x: x.string)

        for string_hash in sorted_string_list:
            event_name = string_hash.string
            event_id = string_hash.hash

            try:
                sound_ids = self._find_sound_ids_for_event(event_id)
                if sound_ids:
                    # 确保音频ID列表是排序的
                    forward_mapping[event_name] = sorted(sound_ids)
            except Exception:
                # 忽略个别事件的错误，继续处理其他事件
                continue

        # 返回AudioMapping实例，会自动构建反向映射
        return AudioMapping(forward_mapping=forward_mapping, reverse_mapping={})

    def _extract_event_strings(self) -> List:
        """
        从输入源中提取事件字符串

        :return: StringHash对象列表
        """
        if isinstance(self.events_input, BIN):
            # BIN文件模式：遍历所有AudioGroup和EventData提取事件
            string_list = []
            for bank in self.events_input.data:
                for unit in bank.bank_units:
                    string_list.extend(unit.events)
            return string_list
        else:
            # 字符串数组模式：创建StringHash对象
            from ..formats.bin.models import StringHash

            string_hashes = []
            for event_name in self.events_input:
                event_hash = str_fnv_32(event_name)
                string_hash = StringHash(string=event_name, hash=event_hash)
                string_hashes.append(string_hash)
            return string_hashes

    def _build_unified_index(self) -> Dict[int, tuple]:
        """
        构建所有HIRC对象的统一索引，用于快速查找

        :return: {对象ID: (对象类型, 对象实例)} 的索引字典
        """
        unified_index = {}

        # 遍历所有资源文件
        for bank in self.hirc.banks.values():
            # 索引事件对象
            for event_id, event_obj in bank.events.items():
                unified_index[event_id] = ("event", event_obj)

            # 索引动作对象
            for action_id, action_obj in bank.event_actions.items():
                unified_index[action_id] = ("action", action_obj)

            # 索引声音对象
            for sound_id, sound_obj in bank.sounds.items():
                unified_index[sound_id] = ("sound", sound_obj)

            # 索引随机容器对象
            for container_id, container_obj in bank.random_containers.items():
                unified_index[container_id] = ("random_container", container_obj)

            # 索引切换容器对象
            for container_id, container_obj in bank.switch_containers.items():
                unified_index[container_id] = ("switch_container", container_obj)

            # 索引音乐段对象
            for container_id, container_obj in getattr(bank, "music_segments", {}).items():
                unified_index[container_id] = ("music_segment", container_obj)

            # 索引音乐播放列表对象
            for container_id, container_obj in getattr(
                bank, "music_playlist_containers", {}
            ).items():
                unified_index[container_id] = ("music_playlist_container", container_obj)

            # 索引音乐切换对象
            for container_id, container_obj in getattr(
                bank, "music_switch_containers", {}
            ).items():
                unified_index[container_id] = ("music_switch_container", container_obj)

            # 索引音乐轨道对象
            for track_id, track_obj in getattr(bank, "music_tracks", {}).items():
                unified_index[track_id] = ("music_track", track_obj)

        return unified_index

    def _find_sound_ids_for_event(self, event_id: int) -> List[int]:
        """
        使用BFS算法查找指定事件ID对应的所有音频文件ID

        :param event_id: 事件ID
        :return: 音频文件ID列表
        """
        if event_id not in self._object_index:
            return []

        sound_ids = []
        visited = set()
        queue = deque([event_id])

        while queue:
            current_id = queue.popleft()

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id not in self._object_index:
                continue

            obj_type, obj = self._object_index[current_id]

            if obj_type == "event":
                # 事件对象：将所有动作ID加入队列
                queue.extend(obj.event_ids)

            elif obj_type == "action":
                # 动作对象：获取目标ID并加入队列
                target_id = self._get_action_target_id(obj)
                if target_id:
                    queue.append(target_id)

            elif obj_type == "sound":
                # 声音对象：直接收集源ID（音频文件ID）
                if hasattr(obj, "source_id") and obj.source_id != 0:
                    sound_ids.append(obj.source_id)

            elif obj_type in (
                "random_container",
                "switch_container",
                "music_segment",
                "music_playlist_container",
                "music_switch_container",
            ):
                # 容器对象：将所有子ID加入队列
                if hasattr(obj, "child_ids"):
                    queue.extend(obj.child_ids)

            elif obj_type == "music_track":
                file_ids = getattr(obj, "file_ids", [])
                sound_ids.extend(file_id for file_id in file_ids if file_id != 0)

        return sorted(list(set(sound_ids)))  # 去重并排序

    def _get_action_target_id(self, action_obj) -> Optional[int]:
        """
        获取动作对象的目标ID

        :param action_obj: 动作对象
        :return: 目标ID或None
        """
        if hasattr(action_obj, "id_ext") and action_obj.id_ext is not None:
            return action_obj.id_ext
        return None


class MappingAnalyzer:
    """
    映射分析器

    职责：对AudioMapping实例进行各种分析，返回分析结果字典。
    专注于数据分析功能，不涉及数据构建和IO操作。
    """

    def __init__(self, mapping: AudioMapping):
        """
        初始化映射分析器

        :param mapping: AudioMapping实例
        """
        self.mapping = mapping

    def analyze_file_coverage(self, actual_files: List[str]) -> Dict[str, any]:
        """
        分析映射覆盖率

        :param actual_files: 实际存在的音频文件ID列表(字符串格式)
        :return: 覆盖率分析结果字典
        """
        # 转换文件ID为整数集合
        actual_file_ids = set(int(file_id) for file_id in actual_files)

        # 获取映射中的音频文件ID
        categorized_file_ids = self.mapping.get_all_sound_ids()

        # 计算各种集合
        uncategorized = actual_file_ids - categorized_file_ids  # 存在但未分类
        categorized = actual_file_ids & categorized_file_ids  # 存在且已分类
        mapping_not_exist = (
            categorized_file_ids - actual_file_ids
        )  # 映射中存在但实际不存在

        total_files = len(actual_file_ids)
        coverage_rate = len(categorized) / total_files * 100 if total_files > 0 else 0

        return {
            "total_files": total_files,
            "categorized_count": len(categorized),
            "uncategorized_count": len(uncategorized),
            "coverage_rate": round(coverage_rate, 2),
            "uncategorized_files": sorted(list(uncategorized)),
            "mapping_not_exist": sorted(list(mapping_not_exist)),
            "categorized_files": sorted(list(categorized)),
        }

    def analyze_event_complexity(self) -> Dict[str, any]:
        """
        分析事件复杂度（每个事件包含的音频文件数量）

        :return: 事件复杂度分析结果字典
        """
        sound_counts = [len(sounds) for sounds in self.mapping.forward_mapping.values()]

        if not sound_counts:
            return {
                "total_events": 0,
                "simple_events": 0,
                "complex_events": 0,
                "avg_sounds_per_event": 0,
                "max_sounds_per_event": 0,
                "min_sounds_per_event": 0,
            }

        simple_events = sum(1 for count in sound_counts if count == 1)
        complex_events = sum(1 for count in sound_counts if count > 1)

        return {
            "total_events": len(sound_counts),
            "simple_events": simple_events,  # 只包含1个音频文件的事件
            "complex_events": complex_events,  # 包含多个音频文件的事件
            "avg_sounds_per_event": round(sum(sound_counts) / len(sound_counts), 2),
            "max_sounds_per_event": max(sound_counts),
            "min_sounds_per_event": min(sound_counts),
        }

    def analyze_sound_reuse(self) -> Dict[str, any]:
        """
        分析音频文件重用情况（同一个音频文件被多少个事件使用）

        :return: 音频重用分析结果字典
        """
        event_counts = [len(events) for events in self.mapping.reverse_mapping.values()]

        if not event_counts:
            return {
                "total_sounds": 0,
                "unique_sounds": 0,
                "reused_sounds": 0,
                "avg_events_per_sound": 0,
                "max_events_per_sound": 0,
                "min_events_per_sound": 0,
            }

        unique_sounds = sum(1 for count in event_counts if count == 1)
        reused_sounds = sum(1 for count in event_counts if count > 1)

        return {
            "total_sounds": len(event_counts),
            "unique_sounds": unique_sounds,  # 只被1个事件使用的音频文件
            "reused_sounds": reused_sounds,  # 被多个事件使用的音频文件
            "avg_events_per_sound": round(sum(event_counts) / len(event_counts), 2),
            "max_events_per_sound": max(event_counts),
            "min_events_per_sound": min(event_counts),
        }

    def get_comprehensive_analysis(
        self, actual_files: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        获取综合分析报告

        :param actual_files: 实际存在的音频文件ID列表，可选
        :return: 综合分析结果字典
        """
        analysis = {
            "mapping_stats": self.mapping.stats,
            "sound_usage_stats": self.mapping.get_sound_usage_stats(),
            "event_complexity": self.analyze_event_complexity(),
            "sound_reuse": self.analyze_sound_reuse(),
        }

        if actual_files:
            analysis["file_coverage"] = self.analyze_file_coverage(actual_files)

        return analysis
