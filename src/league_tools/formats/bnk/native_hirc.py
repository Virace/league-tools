# 🐍 Beautiful is better than ugly.
# 🐼 优美优于丑陋
# @Author  : Codex
# @Detail  : 原生 HIRC 二进制解析

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union

from loguru import logger

from league_tools.core.binary import BinaryReader
from league_tools.formats.bnk.section.HIRC import (
    Action,
    Event,
    HIRCType,
    MusicRandomCntr,
    MusicSegmentCntr,
    MusicSwitchCntr,
    MusicTrack,
    RanSeqCntr,
    Sound,
    SwitchCntr,
)


class NativeHIRCError(Exception):
    """Native HIRC 解析错误。"""


@dataclass
class NativeBank:
    """单个 BNK 的最小 HIRC 对象集合。"""

    filename: str
    path: Optional[str] = None
    version: Optional[int] = None
    events: Dict[int, Event] = field(default_factory=dict)
    event_actions: Dict[int, Action] = field(default_factory=dict)
    sounds: Dict[int, Sound] = field(default_factory=dict)
    random_containers: Dict[int, RanSeqCntr] = field(default_factory=dict)
    switch_containers: Dict[int, SwitchCntr] = field(default_factory=dict)
    music_segments: Dict[int, MusicSegmentCntr] = field(default_factory=dict)
    music_playlist_containers: Dict[int, MusicRandomCntr] = field(default_factory=dict)
    music_switch_containers: Dict[int, MusicSwitchCntr] = field(default_factory=dict)
    music_tracks: Dict[int, MusicTrack] = field(default_factory=dict)

    def stats(self) -> Dict[str, int]:
        """返回当前 bank 的对象统计。"""

        return {
            "events": len(self.events),
            "actions": len(self.event_actions),
            "sounds": len(self.sounds),
            "random_containers": len(self.random_containers),
            "switch_containers": len(self.switch_containers),
            "music_segments": len(self.music_segments),
            "music_playlist_containers": len(self.music_playlist_containers),
            "music_switch_containers": len(self.music_switch_containers),
            "music_tracks": len(self.music_tracks),
        }


@dataclass
class _BaseParams:
    """容器类对象共享的最小基础参数。"""

    bus_id: int
    parent_id: int


class NativeHIRC:
    """直接从 BNK HIRC 区块构建的兼容对象图。"""

    __slots__ = ["banks", "_use_cache", "_cache_dir"]

    def __init__(
        self,
        file_path: Optional[Union[str, Path]] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
    ) -> None:
        self.banks: Dict[str, NativeBank] = {}
        self._use_cache = use_cache
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None

        if file_path is not None:
            self.load_file(file_path)

    @classmethod
    def from_bnk(
        cls,
        bnk_file: Union[str, Path],
        cache_dir: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
    ) -> "NativeHIRC":
        """从 BNK 文件创建 NativeHIRC 实例。"""

        return cls(bnk_file, cache_dir=cache_dir, use_cache=use_cache)

    def add_bank(self, bank: NativeBank) -> None:
        """添加已解析的 bank。"""

        self.banks[bank.filename] = bank

    def load_file(self, file_path: Union[str, Path]) -> None:
        """加载并解析单个 BNK 文件。"""

        path = Path(file_path)
        if not path.exists():
            raise NativeHIRCError(f"文件不存在: {path}")

        bank = NativeBank(filename=path.name, path=str(path))
        reader = BinaryReader(path)
        try:
            self._parse_sections(reader, bank)
        finally:
            reader.close()

        self.add_bank(bank)

    def _parse_sections(self, reader: BinaryReader, bank: NativeBank) -> None:
        """读取 BKHD/HIRC 区块。"""

        while not reader.is_end():
            header = reader.customize("<4sI", False)
            if not header:
                break
            section_id, section_size = header
            section_reader = reader.binary(section_size)

            if section_id == b"BKHD":
                bank.version = self._read_u32(section_reader, "BKHD.bank_version")
            elif section_id == b"HIRC":
                self._parse_hirc_section(section_reader, bank)

    def _parse_hirc_section(self, reader: BinaryReader, bank: NativeBank) -> None:
        """解析 HIRC 区块内的对象。"""

        object_count = self._read_u32(reader, "HIRC.object_count")
        version = bank.version or 145

        for _ in range(object_count):
            object_type = self._read_u8(reader, "HIRC.object_type")
            section_size = self._read_u32(reader, "HIRC.section_size")
            object_reader = reader.binary(section_size)
            self._parse_hirc_object(object_type, object_reader, bank, version)

    def _parse_hirc_object(
        self,
        object_type: int,
        reader: BinaryReader,
        bank: NativeBank,
        version: int,
    ) -> None:
        """按对象类型分发解析。"""

        try:
            hirc_type = HIRCType(object_type)
        except ValueError:
            logger.debug(f"跳过暂未支持的 HIRC 类型: {object_type}")
            return

        if hirc_type == HIRCType.EVENT:
            event = self._parse_event(reader)
            bank.events[event.object_id] = event
            return

        if hirc_type == HIRCType.ACTION:
            action = self._parse_action(reader)
            bank.event_actions[action.object_id] = action
            return

        if hirc_type == HIRCType.SOUND:
            sound = self._parse_sound(reader)
            bank.sounds[sound.object_id] = sound
            return

        if hirc_type == HIRCType.RANDOM_CONTAINER:
            container = self._parse_random_container(reader, version)
            bank.random_containers[container.object_id] = container
            return

        if hirc_type == HIRCType.SWITCH_CONTAINER:
            container = self._parse_switch_container(reader, version)
            bank.switch_containers[container.object_id] = container
            return

        if hirc_type == HIRCType.MUSIC_SEGMENT_CONTAINER:
            container = self._parse_music_segment(reader, version)
            bank.music_segments[container.object_id] = container
            return

        if hirc_type == HIRCType.MUSIC_RANDOM_CONTAINER:
            container = self._parse_music_playlist_container(reader, version)
            bank.music_playlist_containers[container.object_id] = container
            return

        if hirc_type == HIRCType.MUSIC_SWITCH_CONTAINER:
            container = self._parse_music_switch_container(reader, version)
            bank.music_switch_containers[container.object_id] = container
            return

        if hirc_type == HIRCType.MUSIC_TRACK:
            track = self._parse_music_track(reader)
            bank.music_tracks[track.object_id] = track

    def _parse_event(self, reader: BinaryReader) -> Event:
        """解析 Event 对象。"""

        object_id = self._read_u32(reader, "Event.object_id")
        action_count = self._read_u8(reader, "Event.action_count")
        action_ids = [self._read_u32(reader, "Event.action_id") for _ in range(action_count)]
        return Event(object_id=object_id, event_ids=action_ids)

    def _parse_action(self, reader: BinaryReader) -> Action:
        """解析 Action 对象。"""

        object_id = self._read_u32(reader, "Action.object_id")
        scope = self._read_u8(reader, "Action.scope")
        action_type_code = self._read_u8(reader, "Action.action_type")
        action_type = scope | (action_type_code << 8)

        if action_type in (0x1901, 0x1204):
            reader.skip(5)
            count_a = self._read_u8(reader, "Action.count_a")
            reader.skip(5 * count_a)
            count_b = self._read_u8(reader, "Action.count_b")
            reader.skip(9 * count_b)
            first_id = self._read_u32(reader, "Action.first_special_id")
            second_id = self._read_u32(reader, "Action.second_special_id")

            if action_type == 0x1901:
                return Action(
                    object_id=object_id,
                    action_type=action_type,
                    id_ext=None,
                    switch_group_id=first_id,
                    switch_state_id=second_id,
                    state_group_id=None,
                    target_state_id=None,
                )

            return Action(
                object_id=object_id,
                action_type=action_type,
                id_ext=None,
                switch_group_id=None,
                switch_state_id=None,
                state_group_id=first_id,
                target_state_id=second_id,
            )

        target_id = self._read_u32(reader, "Action.target_id")
        return Action(
            object_id=object_id,
            action_type=action_type,
            id_ext=target_id,
            switch_group_id=None,
            switch_state_id=None,
            state_group_id=None,
            target_state_id=None,
        )

    def _parse_sound(self, reader: BinaryReader) -> Sound:
        """解析 Sound 对象。"""

        object_id = self._read_u32(reader, "Sound.object_id")
        reader.skip(4)
        stream_type = self._read_u8(reader, "Sound.stream_type")
        source_id = self._read_u32(reader, "Sound.source_id")
        return Sound(object_id=object_id, source_id=source_id, stream_type=stream_type)

    def _parse_random_container(self, reader: BinaryReader, version: int) -> RanSeqCntr:
        """解析 Random/Sequence Container。"""

        object_id = self._read_u32(reader, "RandomContainer.object_id")
        base_params = self._parse_base_params(reader, version)
        reader.skip(24)
        child_ids = self._read_u32_list(reader, "RandomContainer.child_ids")
        return RanSeqCntr(
            object_id=object_id,
            direct_parent_id=base_params.parent_id,
            child_ids=child_ids,
        )

    def _parse_switch_container(self, reader: BinaryReader, version: int) -> SwitchCntr:
        """解析 Switch Container。"""

        object_id = self._read_u32(reader, "SwitchContainer.object_id")
        base_params = self._parse_base_params(reader, version)
        reader.skip(1)
        if version <= 0x59:
            reader.skip(3)
        reader.skip(4)
        reader.skip(5)
        child_ids = self._read_u32_list(reader, "SwitchContainer.child_ids")
        return SwitchCntr(
            object_id=object_id,
            direct_parent_id=base_params.parent_id,
            child_ids=child_ids,
        )

    def _parse_music_segment(self, reader: BinaryReader, version: int) -> MusicSegmentCntr:
        """解析 Music Segment。"""

        object_id = self._read_u32(reader, "MusicSegment.object_id")
        reader.skip(1)
        base_params = self._parse_base_params(reader, version)
        child_ids = self._read_u32_list(reader, "MusicSegment.child_ids")
        return MusicSegmentCntr(
            object_id=object_id,
            direct_parent_id=base_params.parent_id,
            child_ids=child_ids,
        )

    def _parse_music_playlist_container(
        self, reader: BinaryReader, version: int
    ) -> MusicRandomCntr:
        """解析 Music Playlist Container。"""

        object_id = self._read_u32(reader, "MusicPlaylist.object_id")
        reader.skip(1)
        base_params = self._parse_base_params(reader, version)
        child_ids = self._read_u32_list(reader, "MusicPlaylist.child_ids")
        return MusicRandomCntr(
            object_id=object_id,
            direct_parent_id=base_params.parent_id,
            child_ids=child_ids,
        )

    def _parse_music_switch_container(
        self, reader: BinaryReader, version: int
    ) -> MusicSwitchCntr:
        """解析 Music Switch Container。"""

        object_id = self._read_u32(reader, "MusicSwitch.object_id")
        reader.skip(1)
        base_params = self._parse_base_params(reader, version)
        child_ids = self._read_u32_list(reader, "MusicSwitch.child_ids")
        reader.skip(23)
        stinger_count = self._read_u32(reader, "MusicSwitch.stinger_count")
        reader.skip(24 * stinger_count)
        rule_count = self._read_u32(reader, "MusicSwitch.rule_count")

        for _ in range(rule_count):
            source_count = self._read_u32(reader, "MusicSwitch.rule_source_count")
            reader.skip(4 * source_count)
            destination_count = self._read_u32(
                reader, "MusicSwitch.rule_destination_count"
            )
            reader.skip(4 * destination_count)
            reader.skip(45 if version <= 145 else 47)
            has_transition = self._read_u8(reader, "MusicSwitch.has_transition")
            if has_transition:
                reader.skip(30)

        return MusicSwitchCntr(
            object_id=object_id,
            direct_parent_id=base_params.parent_id,
            child_ids=child_ids,
        )

    def _parse_music_track(self, reader: BinaryReader) -> MusicTrack:
        """解析 Music Track。"""

        object_id = self._read_u32(reader, "MusicTrack.object_id")
        reader.skip(1)
        playlist_item_count = self._read_u32(reader, "MusicTrack.playlist_item_count")
        reader.skip(14 * playlist_item_count)
        source_count = self._read_u32(reader, "MusicTrack.source_count")
        file_ids = []

        for _ in range(source_count):
            reader.skip(4)
            file_ids.append(self._read_u32(reader, "MusicTrack.file_id"))
            reader.skip(36)

        return MusicTrack(object_id=object_id, file_ids=file_ids)

    def _parse_base_params(self, reader: BinaryReader, version: int) -> _BaseParams:
        """消费容器类对象共同的 BaseParams。"""

        self._skip_fx(reader, version)
        bus_id = self._read_u32(reader, "BaseParams.bus_id")
        parent_id = self._read_u32(reader, "BaseParams.parent_id")
        reader.skip(2 if version <= 89 else 1)
        self._skip_init_params(reader)
        self._skip_pos_params(reader, version)
        self._skip_aux(reader, version)
        self._skip_state_groups(reader)
        self._skip_rtpc(reader, version)
        return _BaseParams(bus_id=bus_id, parent_id=parent_id)

    def _skip_fx(self, reader: BinaryReader, version: int) -> None:
        """跳过 BaseParams 的 Fx 配置。"""

        reader.skip(1)
        fx_count = self._read_u8(reader, "BaseParams.fx_count")
        if fx_count > 0:
            reader.skip(1 + fx_count * (7 if version <= 145 else 6))

        if version > 136:
            reader.skip(1)
            fx_count = self._read_u8(reader, "BaseParams.extra_fx_count")
            if fx_count > 0:
                reader.skip(6 * fx_count)

        if 89 < version <= 145:
            reader.skip(1)

    def _skip_init_params(self, reader: BinaryReader) -> None:
        """跳过 InitParams。"""

        count_a = self._read_u8(reader, "BaseParams.init_count_a")
        reader.skip(5 * count_a)
        count_b = self._read_u8(reader, "BaseParams.init_count_b")
        reader.skip(9 * count_b)

    def _skip_pos_params(self, reader: BinaryReader, version: int) -> None:
        """跳过 PosParams。"""

        pos_bits = self._read_u8(reader, "BaseParams.pos_bits")
        has_pos = bool(pos_bits & 0x01)
        has_3d = bool(pos_bits & 0x02)
        has_automation = bool((pos_bits >> 5) & 0x03)

        if has_pos and has_3d:
            reader.skip(1)

        if has_automation:
            reader.skip(5)
            count_a = self._read_u32(reader, "BaseParams.pos_count_a")
            reader.skip(16 * count_a)
            count_b = self._read_u32(reader, "BaseParams.pos_count_b")
            reader.skip((16 if version <= 0x59 else 20) * count_b)

    def _skip_aux(self, reader: BinaryReader, version: int) -> None:
        """跳过 Aux 配置。"""

        flags = self._read_u8(reader, "BaseParams.aux_flags")
        if (flags >> 3) & 0x01:
            reader.skip(16)
        if version > 135:
            reader.skip(4)

    def _skip_state_groups(self, reader: BinaryReader) -> None:
        """跳过 StateGroups。"""

        reader.skip(6)
        count_a = self._read_u8(reader, "BaseParams.state_count_a")
        reader.skip(3 * count_a)
        count_b = self._read_u8(reader, "BaseParams.state_count_b")

        for _ in range(count_b):
            reader.skip(5)
            inner_count = self._read_u8(reader, "BaseParams.state_inner_count")
            reader.skip(8 * inner_count)

    def _skip_rtpc(self, reader: BinaryReader, version: int) -> None:
        """跳过 RTPC。"""

        rtpc_count = self._read_u16(reader, "BaseParams.rtpc_count")
        header_skip = 13 if version <= 89 else 12

        for _ in range(rtpc_count):
            reader.skip(header_skip)
            point_count = self._read_u16(reader, "BaseParams.rtpc_point_count")
            reader.skip(12 * point_count)

    def _read_u32_list(self, reader: BinaryReader, field_name: str) -> list[int]:
        """读取以 count 开头的 u32 列表。"""

        count = self._read_u32(reader, f"{field_name}.count")
        if count == 0:
            return []

        values = reader.customize(f"<{count}I", False)
        if values is None:
            raise NativeHIRCError(f"读取 {field_name} 失败")
        return list(values)

    def _read_u8(self, reader: BinaryReader, field_name: str) -> int:
        """读取 u8 并确保非空。"""

        value = reader.customize("<B")
        if value is None:
            raise NativeHIRCError(f"读取 {field_name} 失败")
        return int(value)

    def _read_u16(self, reader: BinaryReader, field_name: str) -> int:
        """读取 u16 并确保非空。"""

        value = reader.customize("<H")
        if value is None:
            raise NativeHIRCError(f"读取 {field_name} 失败")
        return int(value)

    def _read_u32(self, reader: BinaryReader, field_name: str) -> int:
        """读取 u32 并确保非空。"""

        value = reader.customize("<I")
        if value is None:
            raise NativeHIRCError(f"读取 {field_name} 失败")
        return int(value)
