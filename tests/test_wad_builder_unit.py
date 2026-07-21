from __future__ import annotations

import struct
from pathlib import Path

import xxhash

from league_tools.formats.wad.builder import WADBuilder, pack_entry_v34
from league_tools.formats.wad.parser import WAD


def test_pack_entry_v34_matches_parser_layout() -> None:
    raw = pack_entry_v34(
        path_hash=0xAABBCCDD11223344,
        offset=272,
        compressed_size=10,
        size=20,
        entry_type=3,
        subchunk_count=2,
        subchunk_index=0x123456,
        checksum=0x99,
    )
    assert len(raw) == 32
    path_hash, offset, comp, size, type_byte, hi, lo16, checksum = struct.unpack('<QIIIBBHQ', raw)
    assert path_hash == 0xAABBCCDD11223344
    assert (offset, comp, size) == (272, 10, 20)
    assert type_byte & 0xF == 3
    assert (type_byte & 0xF0) >> 4 == 2
    assert lo16 + (hi << 16) == 0x123456
    assert checksum == 0x99


def test_builder_roundtrip_via_parser(tmp_path: Path) -> None:
    payload_json = b'{"enabled": true}' * 50
    payload_bnk = b'BKHD' + b'\x01' * 100
    out = (
        WADBuilder()
        .add('plugins/demo/config.json', payload_json)
        .add('assets/sounds/demo.bnk', payload_bnk)
        .save(tmp_path / 'demo.wad.client')
    )

    wad = WAD(str(out))
    assert wad.version == [3, 4]
    assert len(wad.files) == 2
    assert wad.extract(['plugins/demo/config.json', 'assets/sounds/demo.bnk'], raw=True) == [
        payload_json,
        payload_bnk,
    ]

    by_hash = {f.path_hash: f for f in wad.files}
    json_entry = by_hash[WAD.get_hash_v34('plugins/demo/config.json')]
    bnk_entry = by_hash[WAD.get_hash_v34('assets/sounds/demo.bnk')]
    assert json_entry.type == 3
    assert bnk_entry.type == 0
    assert bnk_entry.compressed_size == len(payload_bnk)


def test_builder_toc_sorted_dedup_and_checksum(tmp_path: Path) -> None:
    same = b'same-content' * 10
    data = (
        WADBuilder()
        .add('zzz/b.txt', same)
        .add('aaa/a.txt', same)
        .add('mmm/c.txt', b'unique')
        .to_bytes()
    )

    wad = WAD(data)
    hashes = [f.path_hash for f in wad.files]
    assert hashes == sorted(hashes)

    by_hash = {f.path_hash: f for f in wad.files}
    entry_a = by_hash[WAD.get_hash_v34('aaa/a.txt')]
    entry_b = by_hash[WAD.get_hash_v34('zzz/b.txt')]
    assert entry_a.offset == entry_b.offset

    stored = data[entry_a.offset:entry_a.offset + entry_a.compressed_size]
    assert entry_a.sha256 == xxhash.xxh3_64_intdigest(stored)


def test_builder_add_overwrites_same_path_and_accepts_file(tmp_path: Path) -> None:
    src_file = tmp_path / 'payload.json'
    src_file.write_bytes(b'{"v": 2}')

    builder = WADBuilder()
    builder.add('cfg/a.json', b'{"v": 1}')
    builder.add('cfg/a.json', src_file)
    wad = WAD(builder.to_bytes())
    assert len(wad.files) == 1
    assert wad.extract(['cfg/a.json'], raw=True) == [b'{"v": 2}']


def test_builder_empty_produces_parseable_wad() -> None:
    wad = WAD(WADBuilder().to_bytes())
    assert wad.version == [3, 4]
    assert wad.files == []
