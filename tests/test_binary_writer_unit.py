from __future__ import annotations

import struct
from pathlib import Path

import pytest

from league_tools.core.binary import BinaryWriter


def test_binary_writer_memory_roundtrip() -> None:
    with BinaryWriter() as bw:
        bw.customize('<QI', 0x1122334455667788, 42)
        bw.bytes(b'abc')
        assert bw.tell() == 15
        bw.seek(8)
        bw.customize('<I', 99)
        data = bw.getvalue()
    assert struct.unpack_from('<Q', data, 0)[0] == 0x1122334455667788
    assert struct.unpack_from('<I', data, 8)[0] == 99
    assert data[12:15] == b'abc'


def test_binary_writer_file_output(tmp_path: Path) -> None:
    out = tmp_path / 'out.bin'
    with BinaryWriter(out) as bw:
        bw.bytes(b'\x00' * 4)
        bw.seek(0)
        bw.customize('<I', 7)
    assert out.read_bytes() == struct.pack('<I', 7)


def test_binary_writer_getvalue_rejects_file_mode(tmp_path: Path) -> None:
    with BinaryWriter(tmp_path / 'x.bin') as bw:
        with pytest.raises(TypeError):
            bw.getvalue()
