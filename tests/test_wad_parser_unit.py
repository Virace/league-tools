from __future__ import annotations

import gzip
import struct
from pathlib import Path

import pytest
import zstd

from league_tools.formats.wad.parser import MalformedSubchunkError, WAD, WADSection


def _new_wad(version: list[int] | None = None) -> WAD:
    wad = object.__new__(WAD)
    wad.version = version or [3, 4]
    wad.files = []
    return wad


def test_wad_hash_algorithm_switches_by_version(monkeypatch: pytest.MonkeyPatch) -> None:
    wad = _new_wad([3, 4])
    calls: list[str] = []

    def fake_v34(path: str) -> int:
        calls.append(f"v34:{path}")
        return 111

    def fake_legacy(path: str) -> int:
        calls.append(f"legacy:{path}")
        return 222

    monkeypatch.setattr(WAD, "get_hash_v34", staticmethod(fake_v34))
    monkeypatch.setattr(WAD, "get_hash", staticmethod(fake_legacy))

    assert wad._get_hash_for_path("A/B") == 111
    assert calls == ["v34:A/B"]

    wad.version = [3, 3]
    assert wad._get_hash_for_path("A/B") == 222
    assert calls[-1] == "legacy:A/B"


def test_decompress_subchunks_supports_plain_and_zstd() -> None:
    wad = _new_wad()

    raw_plain = b"ABCD"
    plain_blob = struct.pack("<II", len(raw_plain), len(raw_plain)) + raw_plain
    plain_section = WADSection(
        path_hash=1,
        offset=0,
        compressed_size=len(plain_blob),
        size=len(raw_plain),
        type=0x14,
    )
    assert wad._decompress_subchunks(plain_section, plain_blob) == raw_plain

    raw_zstd = b"hello-zstd"
    compressed = zstd.compress(raw_zstd)
    zstd_blob = struct.pack("<II", len(compressed), len(raw_zstd)) + compressed
    zstd_section = WADSection(
        path_hash=2,
        offset=0,
        compressed_size=len(zstd_blob),
        size=len(raw_zstd),
        type=0x14,
    )
    assert wad._decompress_subchunks(zstd_section, zstd_blob) == raw_zstd


def test_extract_by_section_handles_all_main_branches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wad = _new_wad()

    # type=0 不压缩
    section_raw = WADSection(1, 0, 3, 3, 0)
    assert wad.extract_by_section(section_raw, tmp_path / "raw.bin", raw=True, data=b"abc") == b"abc"

    # type=1 gzip
    payload = b"gzip-payload"
    gzip_data = gzip.compress(payload)
    section_gzip = WADSection(2, 0, len(gzip_data), len(payload), 1)
    assert wad.extract_by_section(section_gzip, tmp_path / "gzip.bin", raw=True, data=gzip_data) == payload

    # type=3 zstd
    zstd_data = zstd.compress(payload)
    section_zstd = WADSection(3, 0, len(zstd_data), len(payload), 3)
    assert wad.extract_by_section(section_zstd, tmp_path / "zstd.bin", raw=True, data=zstd_data) == payload

    # type=4 子块
    section_subchunk = WADSection(4, 0, 5, 5, 0x14)
    monkeypatch.setattr(wad, "_decompress_subchunks", lambda *_args, **_kwargs: b"12345")
    assert (
        wad.extract_by_section(section_subchunk, tmp_path / "subchunk.bin", raw=True, data=b"dummy")
        == b"12345"
    )

    # type=4 子块异常 -> 返回None
    def _raise_malformed(*_args, **_kwargs):
        raise MalformedSubchunkError("broken")

    monkeypatch.setattr(wad, "_decompress_subchunks", _raise_malformed)
    assert wad.extract_by_section(section_subchunk, tmp_path / "broken.bin", raw=True, data=b"dummy") is None

    # 不支持的类型 -> 返回None
    section_unknown = WADSection(5, 0, 3, 3, 9)
    assert wad.extract_by_section(section_unknown, tmp_path / "unknown.bin", raw=True, data=b"abc") is None

    # raw=False 写文件
    out_path = tmp_path / "write.bin"
    saved = wad.extract_by_section(section_raw, out_path, raw=False, data=b"abc")
    assert saved == out_path
    assert out_path.read_bytes() == b"abc"


def test_extract_requires_out_dir_when_raw_is_false() -> None:
    wad = _new_wad()
    with pytest.raises(ValueError):
        wad.extract(["assets/test.bin"], out_dir="", raw=False)


def test_extract_uses_hash_index_and_callable_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wad = _new_wad()
    wad.files = [WADSection(path_hash=123, offset=0, compressed_size=1, size=1, type=0)]

    def fake_hash(path: str) -> int:
        return 123 if path == "exists.bin" else 999

    def fake_extract(file_obj, file_path, raw=False, data=None):
        assert file_obj.path_hash == 123
        return f"ok:{Path(file_path).name}"

    monkeypatch.setattr(wad, "_get_hash_for_path", fake_hash)
    monkeypatch.setattr(wad, "extract_by_section", fake_extract)

    results = wad.extract(
        ["exists.bin", "missing.bin"],
        out_dir=lambda p: tmp_path / "out" / p,
        raw=False,
    )
    assert results == ["ok:exists.bin", None]
