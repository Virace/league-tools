from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest

from league_tools import AudioEventMapper, BIN, BNK, WPK, WwiserHIRC
from league_tools.utils.wwiser import WwiserManager


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "external"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"

REQUIRED_FILE_KEYS = (
    "bin",
    "sfx_audio_bnk",
    "sfx_events_bnk",
    "vo_audio_bnk",
    "vo_events_bnk",
    "vo_audio_wpk",
)


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        pytest.skip(f"未找到样本清单：{MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def manifest_data() -> dict:
    manifest = _load_manifest()
    champions = manifest.get("champions", [])
    if not champions:
        pytest.skip("manifest 中无已提取英雄")
    return manifest


def _entry_paths(entry: dict) -> dict[str, Path]:
    files = entry.get("files", {})
    return {key: FIXTURE_ROOT / value for key, value in files.items()}


@lru_cache(maxsize=128)
def _parse_bin(path: str) -> BIN:
    return BIN(path)


@lru_cache(maxsize=128)
def _parse_bnk(path: str) -> BNK:
    return BNK(path)


@lru_cache(maxsize=128)
def _parse_wpk(path: str) -> WPK:
    return WPK(path)


@lru_cache(maxsize=1)
def _get_wwiser_manager() -> WwiserManager:
    return WwiserManager(auto_download=False)


@lru_cache(maxsize=128)
def _parse_hirc_from_bnk(path: str) -> WwiserHIRC:
    wwiser_manager = _get_wwiser_manager()
    return WwiserHIRC.from_bnk(path, wwiser_manager=wwiser_manager, use_cache=False)


def _collect_bin_bank_paths(bin_obj: BIN) -> set[str]:
    paths: set[str] = set()
    for group in bin_obj.data:
        for unit in group.bank_units:
            for bank_path in unit.bank_path:
                paths.add(Path(bank_path).name.lower())
    return paths


def _collect_bin_vo_events(bin_obj: BIN) -> list[str]:
    events: list[str] = []
    for group in bin_obj.data:
        for unit in group.bank_units:
            if "vo" not in unit.category.lower():
                continue
            events.extend(item.string for item in unit.events)
    return events


def _extract_positive_wem_ids_from_bnk(bnk_obj: BNK) -> set[int]:
    return {wem.id for wem in bnk_obj.extract_files() if wem.id > 0}


def _extract_positive_wem_ids_from_wpk(wpk_obj: WPK) -> set[int]:
    return {wem.id for wem in wpk_obj.extract_files() if wem.id > 0}


def test_manifest_entries_have_required_audio_files(manifest_data: dict) -> None:
    for entry in manifest_data["champions"]:
        champion = entry.get("champion", "<unknown>")
        files = entry.get("files", {})
        for key in REQUIRED_FILE_KEYS:
            assert key in files, f"{champion} 缺少清单字段: {key}"
            path = FIXTURE_ROOT / files[key]
            assert path.exists(), f"{champion} 缺少文件: {path}"
        assert entry.get("missing", []) == [], f"{champion} 存在未提取项"


def test_bin_paths_match_manifest_audio_files(manifest_data: dict) -> None:
    for entry in manifest_data["champions"]:
        champion = entry["champion"]
        paths = _entry_paths(entry)
        bin_obj = _parse_bin(str(paths["bin"]))

        total_events = sum(len(unit.events) for group in bin_obj.data for unit in group.bank_units)
        categories = [unit.category for group in bin_obj.data for unit in group.bank_units]

        assert bin_obj.data, f"{champion} BIN 未解析到音频组"
        assert categories, f"{champion} BIN 未解析到类别"
        assert total_events > 0, f"{champion} BIN 未解析到事件"
        assert any("sfx" in category.lower() for category in categories), f"{champion} BIN 缺少 SFX 类别"
        assert any("vo" in category.lower() for category in categories), f"{champion} BIN 缺少 VO 类别"

        bin_bank_names = _collect_bin_bank_paths(bin_obj)
        for key in ("sfx_audio_bnk", "sfx_events_bnk", "vo_audio_bnk", "vo_events_bnk", "vo_audio_wpk"):
            expected_name = paths[key].name.lower()
            assert expected_name in bin_bank_names, f"{champion} BIN 中未引用 {expected_name}"


def test_bnk_and_wpk_have_valid_wem_entries(manifest_data: dict) -> None:
    for entry in manifest_data["champions"]:
        champion = entry["champion"]
        paths = _entry_paths(entry)

        sfx_audio_bnk = _parse_bnk(str(paths["sfx_audio_bnk"]))
        sfx_events_bnk = _parse_bnk(str(paths["sfx_events_bnk"]))
        vo_audio_bnk = _parse_bnk(str(paths["vo_audio_bnk"]))
        vo_events_bnk = _parse_bnk(str(paths["vo_events_bnk"]))
        vo_audio_wpk = _parse_wpk(str(paths["vo_audio_wpk"]))

        assert sfx_audio_bnk.is_version_supported(), f"{champion} sfx_audio_bnk 版本不受支持"
        assert sfx_events_bnk.is_version_supported(), f"{champion} sfx_events_bnk 版本不受支持"
        assert vo_audio_bnk.is_version_supported(), f"{champion} vo_audio_bnk 版本不受支持"
        assert vo_events_bnk.is_version_supported(), f"{champion} vo_events_bnk 版本不受支持"

        sfx_ids = _extract_positive_wem_ids_from_bnk(sfx_audio_bnk)
        vo_audio_bnk_ids = _extract_positive_wem_ids_from_bnk(vo_audio_bnk)
        wpk_ids = _extract_positive_wem_ids_from_wpk(vo_audio_wpk)

        assert sfx_ids, f"{champion} sfx_audio_bnk 未解析出任何 WEM ID"
        assert wpk_ids, f"{champion} vo_audio_wpk 未解析出任何 WEM ID"
        assert vo_audio_wpk.file_count >= len(wpk_ids), f"{champion} WPK file_count 与解析ID数量异常"

        if vo_audio_bnk_ids:
            assert vo_audio_bnk_ids.issubset(wpk_ids), f"{champion} vo_audio_bnk 的WEM ID不在WPK中"


def test_vo_mapping_covers_wpk_ids(manifest_data: dict) -> None:
    wwiser_manager = _get_wwiser_manager()
    if not wwiser_manager.wwiser_path:
        pytest.skip("未找到 wwiser.pyz，跳过 VO 事件映射校验")

    for entry in manifest_data["champions"]:
        champion = entry["champion"]
        paths = _entry_paths(entry)
        bin_obj = _parse_bin(str(paths["bin"]))
        vo_event_names = _collect_bin_vo_events(bin_obj)
        assert vo_event_names, f"{champion} BIN 中无 VO 事件"

        hirc = _parse_hirc_from_bnk(str(paths["vo_events_bnk"]))
        mapping = AudioEventMapper(vo_event_names, hirc).build_mapping()

        mapped_sound_ids = mapping.get_all_sound_ids()
        wpk_ids = _extract_positive_wem_ids_from_wpk(_parse_wpk(str(paths["vo_audio_wpk"])))

        assert mapped_sound_ids, f"{champion} VO 事件未映射到任何声音ID"
        assert wpk_ids.issubset(mapped_sound_ids), f"{champion} WPK 中存在未被 VO 事件映射覆盖的声音ID"
