from __future__ import annotations

from pathlib import Path

import pytest

from league_tools.utils.xml import MultiRootXmlParser


def test_iter_roots_raises_for_missing_file(tmp_path: Path) -> None:
    parser = MultiRootXmlParser()
    missing = tmp_path / "missing.xml"
    with pytest.raises(FileNotFoundError):
        list(parser.iter_roots(missing))


def test_iter_roots_parses_small_file_with_nested_roots(tmp_path: Path) -> None:
    xml_path = tmp_path / "small.xml"
    xml_path.write_text(
        "<banks><root filename='a'/><root filename='b'/></banks>",
        encoding="utf-8",
    )

    parser = MultiRootXmlParser()
    roots = list(parser.iter_roots(xml_path))

    assert [root.get("filename") for root in roots] == ["a", "b"]


def test_process_large_file_parses_multi_root_stream(tmp_path: Path) -> None:
    xml_path = tmp_path / "multi_root.xml"
    xml_path.write_text(
        "<root filename='a'></root><root filename='b'></root>",
        encoding="utf-8",
    )

    parser = MultiRootXmlParser(default_chunk_size=8)
    roots = list(
        parser._process_large_file(
            xml_path,
            filter_func=None,
            chunk_size=8,
            parser_options=parser.default_parser_options,
        )
    )

    assert [root.get("filename") for root in roots] == ["a", "b"]


def test_iter_roots_filter_and_filter_exception(tmp_path: Path) -> None:
    xml_path = tmp_path / "filter.xml"
    xml_path.write_text(
        "<banks><root filename='keep'/><root filename='drop'/></banks>",
        encoding="utf-8",
    )

    parser = MultiRootXmlParser()

    filtered = list(
        parser.iter_roots(
            xml_path, filter_func=lambda attrs: attrs.get("filename") == "keep"
        )
    )
    assert [root.get("filename") for root in filtered] == ["keep"]

    # 过滤函数异常应被吞掉并视为不匹配，不影响整体流程
    skipped = list(
        parser.iter_roots(
            xml_path,
            filter_func=lambda _attrs: (_ for _ in ()).throw(RuntimeError("bad filter")),
        )
    )
    assert skipped == []
