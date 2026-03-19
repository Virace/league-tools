from __future__ import annotations

import struct
from pathlib import Path

from league_tools.formats.bnk.native_hirc import NativeHIRC
from league_tools.tools.audio_mapper import AudioEventMapper
from league_tools.utils.hash import str_fnv_32


def _pack_section(section_id: bytes, payload: bytes) -> bytes:
    return section_id + struct.pack("<I", len(payload)) + payload


def _pack_hirc_object(object_type: int, payload: bytes) -> bytes:
    return struct.pack("<BI", object_type, len(payload)) + payload


def _build_base_params(version: int, parent_id: int = 0, bus_id: int = 0) -> bytes:
    payload = bytearray()
    payload.extend(b"\x00")
    payload.extend(b"\x00")

    if version > 136:
        payload.extend(b"\x00")
        payload.extend(b"\x00")

    if 89 < version <= 145:
        payload.extend(b"\x00")

    payload.extend(struct.pack("<II", bus_id, parent_id))
    payload.extend(b"\x00" if version > 89 else b"\x00\x00")
    payload.extend(b"\x00")
    payload.extend(b"\x00")
    payload.extend(b"\x00")
    payload.extend(b"\x00")

    if version > 135:
        payload.extend(b"\x00" * 4)

    payload.extend(b"\x00" * 6)
    payload.extend(b"\x00")
    payload.extend(b"\x00")
    payload.extend(struct.pack("<H", 0))
    return bytes(payload)


def _build_event_payload(object_id: int, action_ids: list[int]) -> bytes:
    return struct.pack("<IB", object_id, len(action_ids)) + struct.pack(
        f"<{len(action_ids)}I", *action_ids
    )


def _build_action_payload(object_id: int, target_id: int) -> bytes:
    return struct.pack("<IBBI", object_id, 0, 0, target_id)


def _build_sound_payload(object_id: int, wem_id: int) -> bytes:
    return (
        struct.pack("<I", object_id)
        + b"\x00" * 4
        + b"\x00"
        + struct.pack("<I", wem_id)
        + b"\x00" * 8
    )


def _build_random_container_payload(
    version: int, object_id: int, child_ids: list[int], parent_id: int = 0
) -> bytes:
    return (
        struct.pack("<I", object_id)
        + _build_base_params(version=version, parent_id=parent_id)
        + b"\x00" * 24
        + struct.pack("<I", len(child_ids))
        + struct.pack(f"<{len(child_ids)}I", *child_ids)
    )


def _build_switch_container_payload(
    version: int, object_id: int, child_ids: list[int], parent_id: int = 0
) -> bytes:
    return (
        struct.pack("<I", object_id)
        + _build_base_params(version=version, parent_id=parent_id)
        + b"\x00"
        + struct.pack("<I", 0)
        + b"\x00" * 5
        + struct.pack("<I", len(child_ids))
        + struct.pack(f"<{len(child_ids)}I", *child_ids)
    )


def _build_music_segment_payload(
    version: int, object_id: int, child_ids: list[int], parent_id: int = 0
) -> bytes:
    return (
        struct.pack("<I", object_id)
        + b"\x00"
        + _build_base_params(version=version, parent_id=parent_id)
        + struct.pack("<I", len(child_ids))
        + struct.pack(f"<{len(child_ids)}I", *child_ids)
    )


def _build_music_playlist_payload(
    version: int, object_id: int, child_ids: list[int], parent_id: int = 0
) -> bytes:
    return (
        struct.pack("<I", object_id)
        + b"\x00"
        + _build_base_params(version=version, parent_id=parent_id)
        + struct.pack("<I", len(child_ids))
        + struct.pack(f"<{len(child_ids)}I", *child_ids)
    )


def _build_music_switch_payload(
    version: int, object_id: int, child_ids: list[int], parent_id: int = 0
) -> bytes:
    return (
        struct.pack("<I", object_id)
        + b"\x00"
        + _build_base_params(version=version, parent_id=parent_id)
        + struct.pack("<I", len(child_ids))
        + struct.pack(f"<{len(child_ids)}I", *child_ids)
        + b"\x00" * 23
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
    )


def _build_music_track_payload(object_id: int, file_ids: list[int]) -> bytes:
    payload = bytearray()
    payload.extend(struct.pack("<I", object_id))
    payload.extend(b"\x00")
    payload.extend(struct.pack("<I", 0))
    payload.extend(struct.pack("<I", len(file_ids)))

    for index, file_id in enumerate(file_ids):
        payload.extend(struct.pack("<I", index))
        payload.extend(struct.pack("<I", file_id))
        payload.extend(b"\x00" * 36)

    return bytes(payload)


def _build_native_test_bnk() -> bytes:
    version = 145
    event_attack = str_fnv_32("Play_vo_Test_Attack")
    event_move = str_fnv_32("Play_vo_Test_Move")

    objects = [
        _pack_hirc_object(4, _build_event_payload(event_attack, [2001])),
        _pack_hirc_object(4, _build_event_payload(event_move, [2002])),
        _pack_hirc_object(3, _build_action_payload(2001, 3001)),
        _pack_hirc_object(3, _build_action_payload(2002, 3002)),
        _pack_hirc_object(5, _build_random_container_payload(version, 3001, [4001, 6001])),
        _pack_hirc_object(6, _build_switch_container_payload(version, 3002, [4002, 6002])),
        _pack_hirc_object(2, _build_sound_payload(4001, 90001)),
        _pack_hirc_object(2, _build_sound_payload(4002, 90002)),
        _pack_hirc_object(10, _build_music_segment_payload(version, 6001, [6003])),
        _pack_hirc_object(13, _build_music_playlist_payload(version, 6002, [6004])),
        _pack_hirc_object(12, _build_music_switch_payload(version, 6004, [6005])),
        _pack_hirc_object(11, _build_music_track_payload(6003, [91001, 91002])),
        _pack_hirc_object(11, _build_music_track_payload(6005, [92001, 0])),
    ]

    bkhd_payload = struct.pack("<IIII", version, 1, 0, 0)
    hirc_payload = struct.pack("<I", len(objects)) + b"".join(objects)
    return _pack_section(b"BKHD", bkhd_payload) + _pack_section(b"HIRC", hirc_payload)


def _write_test_bnk(tmp_path: Path) -> Path:
    path = tmp_path / "native_hirc_unit_test.bnk"
    path.write_bytes(_build_native_test_bnk())
    return path


def test_native_hirc_parses_minimal_graph(tmp_path: Path) -> None:
    bnk_path = _write_test_bnk(tmp_path)
    hirc = NativeHIRC.from_bnk(bnk_path, use_cache=False)

    bank = hirc.banks[bnk_path.name]

    assert bank.version == 145
    assert sorted(bank.events) == sorted(
        [str_fnv_32("Play_vo_Test_Attack"), str_fnv_32("Play_vo_Test_Move")]
    )
    assert sorted(bank.event_actions) == [2001, 2002]
    assert sorted(bank.sounds) == [4001, 4002]
    assert bank.random_containers[3001].child_ids == [4001, 6001]
    assert bank.switch_containers[3002].child_ids == [4002, 6002]
    assert bank.music_segments[6001].child_ids == [6003]
    assert bank.music_playlist_containers[6002].child_ids == [6004]
    assert bank.music_switch_containers[6004].child_ids == [6005]
    assert bank.music_tracks[6003].file_ids == [91001, 91002]
    assert bank.music_tracks[6005].file_ids == [92001, 0]


def test_audio_event_mapper_supports_native_hirc(tmp_path: Path) -> None:
    bnk_path = _write_test_bnk(tmp_path)
    hirc = NativeHIRC.from_bnk(bnk_path, use_cache=False)

    mapper = AudioEventMapper(
        ["Play_vo_Test_Attack", "Play_vo_Test_Move", "Play_vo_Test_Unknown"],
        hirc,
    )
    mapping = mapper.build_mapping()

    assert mapping.find_sounds_by_event_name("Play_vo_Test_Attack") == [90001, 91001, 91002]
    assert mapping.find_sounds_by_event_name("Play_vo_Test_Move") == [90002, 92001]
    assert mapping.find_sounds_by_event_name("Play_vo_Test_Unknown") == []
