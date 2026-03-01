from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "external"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        pytest.skip(f"未找到样本清单：{MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_file_paths(files: dict) -> list[Path]:
    paths: list[Path] = []
    for value in files.values():
        if isinstance(value, list):
            paths.extend(FIXTURE_ROOT / item for item in value)
        else:
            paths.append(FIXTURE_ROOT / value)
    return paths


def test_manifest_only_contains_extracted_champions() -> None:
    manifest = _load_manifest()
    assert "skipped_incomplete" not in manifest
    assert manifest.get("champions"), "清单中应至少包含一个已提取英雄"


def test_manifest_files_exist() -> None:
    manifest = _load_manifest()
    champions = manifest.get("champions", [])
    assert champions, "清单中无已提取英雄"

    for champion_entry in champions:
        champion_name = champion_entry.get("champion", "<unknown>")
        files = champion_entry.get("files", {})
        assert files, f"{champion_name} 缺少文件映射"
        for file_path in _iter_file_paths(files):
            assert file_path.exists(), f"{champion_name} 缺失文件: {file_path}"
