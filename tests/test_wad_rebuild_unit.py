from __future__ import annotations

from pathlib import Path

import pytest

from league_tools.formats.wad.builder import WADBuilder
from league_tools.formats.wad.parser import WAD

JSON_PATH = 'plugins/demo/config.json'
SHARED_A = 'plugins/demo/shared_a.bin'
SHARED_B = 'plugins/demo/shared_b.bin'
BNK_PATH = 'assets/demo.bnk'

JSON_OLD = b'{"old": true}'
SHARED_DATA = b'shared-data' * 20
BNK_DATA = b'BKHD' + b'\x01' * 64


def _make_source(tmp_path: Path) -> Path:
    return (
        WADBuilder()
        .add(JSON_PATH, JSON_OLD)
        .add(SHARED_A, SHARED_DATA)
        .add(SHARED_B, SHARED_DATA)
        .add(BNK_PATH, BNK_DATA)
        .save(tmp_path / 'src.wad.client')
    )


def _entry_map(wad: WAD) -> dict:
    return {f.path_hash: f for f in wad.files}


def test_rebuild_without_replacements_is_lossless(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    wad = WAD(str(src))
    out = wad.rebuild({}, output=tmp_path / 'copy.wad.client')

    src_wad, out_wad = WAD(str(src)), WAD(str(out))
    src_map, out_map = _entry_map(src_wad), _entry_map(out_wad)
    assert set(src_map) == set(out_map)
    for h, s in src_map.items():
        o = out_map[h]
        assert (o.type, o.size, o.compressed_size, o.sha256) == (s.type, s.size, s.compressed_size, s.sha256)
    paths = [JSON_PATH, SHARED_A, SHARED_B, BNK_PATH]
    assert out_wad.extract(paths, raw=True) == src_wad.extract(paths, raw=True)
    # 共享关系保持：shared_a/shared_b 在新文件中仍指向同一 offset
    assert out_map[WAD.get_hash_v34(SHARED_A)].offset == out_map[WAD.get_hash_v34(SHARED_B)].offset


def test_rebuild_replaces_target_and_keeps_others(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    new_json = b'{"new": 1, "padding": "x"}' * 3
    out = WAD(str(src)).rebuild({JSON_PATH: new_json}, output=tmp_path / 'out.wad.client')

    out_wad = WAD(str(out))
    assert out_wad.version == [3, 4]
    assert out_wad.extract([JSON_PATH, SHARED_A, BNK_PATH], raw=True) == [
        new_json, SHARED_DATA, BNK_DATA,
    ]


def test_rebuild_accepts_hash_key_and_file_source(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    new_file = tmp_path / 'new.json'
    new_file.write_bytes(b'{"from": "file"}')
    out = WAD(str(src)).rebuild(
        {WAD.get_hash_v34(JSON_PATH): new_file},
        output=tmp_path / 'out.wad.client',
    )
    assert WAD(str(out)).extract([JSON_PATH], raw=True) == [b'{"from": "file"}']


def test_rebuild_replacing_shared_entry_keeps_sibling(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    out = WAD(str(src)).rebuild({SHARED_A: b'brand-new'}, output=tmp_path / 'out.wad.client')

    out_wad = WAD(str(out))
    assert out_wad.extract([SHARED_A, SHARED_B], raw=True) == [b'brand-new', SHARED_DATA]
    out_map = _entry_map(out_wad)
    assert out_map[WAD.get_hash_v34(SHARED_A)].offset != out_map[WAD.get_hash_v34(SHARED_B)].offset


def test_rebuild_replacement_follows_original_storage_type(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    new_bnk = b'BKHD' + b'\x02' * 32
    new_json = b'{"z": 1}'
    out = WAD(str(src)).rebuild(
        {BNK_PATH: new_bnk, JSON_PATH: new_json},
        output=tmp_path / 'out.wad.client',
    )

    out_map = _entry_map(WAD(str(out)))
    bnk_entry = out_map[WAD.get_hash(BNK_PATH)]
    assert bnk_entry.type == 0
    assert bnk_entry.compressed_size == len(new_bnk)
    json_entry = out_map[WAD.get_hash(JSON_PATH)]
    assert json_entry.type == 3


def test_rebuild_strict_behaviour_for_missing_target(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    with pytest.raises(KeyError):
        WAD(str(src)).rebuild({'not/exist.json': b'x'}, output=tmp_path / 'o1.wad.client')

    out = WAD(str(src)).rebuild(
        {'not/exist.json': b'x', JSON_PATH: b'{"kept": 1}'},
        output=tmp_path / 'o2.wad.client',
        strict=False,
    )
    assert WAD(str(out)).extract([JSON_PATH], raw=True) == [b'{"kept": 1}']


def test_rebuild_overwrites_source_and_stays_usable(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    wad = WAD(str(src))
    out = wad.rebuild({JSON_PATH: b'{"inplace": true}'})
    assert Path(out) == src
    # 覆盖源文件后，原对象重新打开，可继续使用
    assert wad.extract([JSON_PATH], raw=True) == [b'{"inplace": true}']
    assert WAD(str(src)).extract([JSON_PATH], raw=True) == [b'{"inplace": true}']


def test_rebuild_from_bytes_requires_output(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    wad = WAD(src.read_bytes())
    with pytest.raises(ValueError):
        wad.rebuild({})


def test_rebuild_keeps_entry_sharing_offset_with_empty_entry(tmp_path: Path) -> None:
    # 真实 LCU WAD 中出现过的布局：空条目(compressed_size=0)与真实条目共享
    # 同一 offset，且空条目 hash 排序在前。构造该布局验证透传不丢数据。
    from league_tools.core.binary import BinaryWriter
    from league_tools.formats.wad.builder import entry_checksum, pack_entry_v34

    blob = b'hello-world'
    data_offset = 272 + 2 * 32
    src = tmp_path / 'crafted.wad'
    with BinaryWriter(src) as bw:
        bw.bytes(b'RW')
        bw.customize('<BB', 3, 4)
        bw.bytes(b'\x00' * 256)
        bw.customize('<Q', 0)
        bw.customize('<L', 2)
        bw.bytes(pack_entry_v34(1, data_offset, 0, 0, 0, 0, 0, entry_checksum(b'')))
        bw.bytes(pack_entry_v34(2, data_offset, len(blob), len(blob), 0, 0, 0,
                                entry_checksum(blob)))
        bw.bytes(blob)

    out = WAD(str(src)).rebuild({}, output=tmp_path / 'out.wad')
    out_wad = WAD(str(out))
    out_map = _entry_map(out_wad)
    assert out_wad.extract_by_section(out_map[2], '', raw=True) == blob
    assert out_map[1].compressed_size == 0
