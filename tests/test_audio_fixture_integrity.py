from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest

from league_tools import AudioEventMapper, BIN, BNK, WPK, WwiserHIRC
from league_tools.utils.wwiser import WwiserManager


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "external"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
REPORT_PATH = FIXTURE_ROOT / "full_chain_report.json"

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
    return {key: FIXTURE_ROOT / value for key, value in files.items() if isinstance(value, str)}


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


def _collect_bin_events_by_keyword(bin_obj: BIN, keyword: str) -> list[str]:
    events: set[str] = set()
    for group in bin_obj.data:
        for unit in group.bank_units:
            if keyword not in unit.category.lower():
                continue
            events.update(item.string for item in unit.events)
    return sorted(events)


def _extract_positive_wem_ids_from_bnk(bnk_obj: BNK) -> set[int]:
    return {wem.id for wem in bnk_obj.extract_files() if wem.id > 0}


def _extract_positive_wem_ids_from_wpk(wpk_obj: WPK) -> set[int]:
    return {wem.id for wem in wpk_obj.extract_files() if wem.id > 0}


def _summarize_bin(bin_obj: BIN) -> dict:
    categories: list[str] = []
    category_event_counts: dict[str, int] = {}
    bank_unit_count = 0
    total_event_count = 0

    for group in bin_obj.data:
        for unit in group.bank_units:
            bank_unit_count += 1
            categories.append(unit.category)
            event_count = len(unit.events)
            total_event_count += event_count
            category_event_counts[unit.category] = category_event_counts.get(unit.category, 0) + event_count

    sfx_events = _collect_bin_events_by_keyword(bin_obj, "sfx")
    vo_events = _collect_bin_events_by_keyword(bin_obj, "vo")

    return {
        "is_skin": bool(bin_obj.is_skin),
        "audio_group_count": len(bin_obj.data),
        "bank_unit_count": bank_unit_count,
        "total_event_count": total_event_count,
        "categories": sorted(set(categories)),
        "category_event_counts": dict(sorted(category_event_counts.items())),
        "referenced_bank_files": sorted(_collect_bin_bank_paths(bin_obj)),
        "sfx_event_count": len(sfx_events),
        "vo_event_count": len(vo_events),
        "sfx_event_names": sfx_events,
        "vo_event_names": vo_events,
    }


def _summarize_bnk(bnk_obj: BNK, wem_files: list) -> dict:
    positive_ids = sorted({wem.id for wem in wem_files if wem.id > 0})
    payload_count = sum(1 for wem in wem_files if wem.id > 0 and wem.data)
    return {
        "soundbank_id": bnk_obj.get_soundbank_id(),
        "version": bnk_obj.get_soundbank_version(),
        "language_id": bnk_obj.get_language_id(),
        "version_supported": bnk_obj.is_version_supported(),
        "extracted_file_count": len(wem_files),
        "positive_wem_ids": positive_ids,
        "payload_file_count": payload_count,
    }


def _summarize_wpk(wpk_obj: WPK, wem_files: list) -> dict:
    positive_ids = sorted({wem.id for wem in wem_files if wem.id > 0})
    payload_count = sum(1 for wem in wem_files if wem.id > 0 and wem.data)
    return {
        "version": wpk_obj.version,
        "declared_file_count": wpk_obj.file_count,
        "extracted_file_count": len(wem_files),
        "positive_wem_ids": positive_ids,
        "payload_file_count": payload_count,
    }


def _summarize_hirc(hirc: WwiserHIRC) -> dict:
    totals = {
        "events": 0,
        "actions": 0,
        "sounds": 0,
        "random_containers": 0,
        "switch_containers": 0,
    }
    banks_summary: dict[str, dict] = {}
    sound_source_ids: set[int] = set()

    for bank_name, bank in sorted(hirc.banks.items()):
        stats = bank.stats()
        banks_summary[bank_name] = stats
        for key in totals:
            totals[key] += int(stats.get(key, 0))
        for sound_obj in bank.sounds.values():
            source_id = int(getattr(sound_obj, "source_id", 0))
            if source_id > 0:
                sound_source_ids.add(source_id)

    return {
        "bank_count": len(hirc.banks),
        "banks": banks_summary,
        "totals": totals,
        "sound_source_ids": sorted(sound_source_ids),
    }


def _build_event_mapping_report(
    event_names: list[str],
    hirc: WwiserHIRC,
    available_file_ids: set[int],
) -> dict:
    mapping = AudioEventMapper(event_names, hirc).build_mapping()
    forward_mapping = mapping.forward_mapping
    source_ids = set(available_file_ids)
    mapped_sound_ids = mapping.get_all_sound_ids()

    event_to_file_ids: dict[str, list[int]] = {}
    for event_name in sorted(forward_mapping):
        hit_ids = sorted(
            file_id for file_id in set(forward_mapping[event_name]) if file_id in source_ids
        )
        if hit_ids:
            event_to_file_ids[event_name] = hit_ids

    return {
        "input_event_count": len(event_names),
        "mapped_event_count": len(forward_mapping),
        "source_file_ids": sorted(source_ids),
        "event_to_file_ids": event_to_file_ids,
        "unmatched_source_file_ids": sorted(source_ids - mapped_sound_ids),
    }


def _build_champion_chain_report(entry: dict) -> dict:
    champion = entry["champion"]
    paths = _entry_paths(entry)

    bin_obj = _parse_bin(str(paths["bin"]))
    sfx_audio_bnk = _parse_bnk(str(paths["sfx_audio_bnk"]))
    sfx_events_bnk = _parse_bnk(str(paths["sfx_events_bnk"]))
    vo_audio_bnk = _parse_bnk(str(paths["vo_audio_bnk"]))
    vo_events_bnk = _parse_bnk(str(paths["vo_events_bnk"]))
    vo_audio_wpk = _parse_wpk(str(paths["vo_audio_wpk"]))

    sfx_audio_wems = sfx_audio_bnk.extract_files()
    sfx_events_wems = sfx_events_bnk.extract_files()
    vo_audio_bnk_wems = vo_audio_bnk.extract_files()
    vo_events_wems = vo_events_bnk.extract_files()
    vo_audio_wpk_wems = vo_audio_wpk.extract_files()

    sfx_audio_ids = {wem.id for wem in sfx_audio_wems if wem.id > 0}
    vo_audio_wpk_ids = {wem.id for wem in vo_audio_wpk_wems if wem.id > 0}

    sfx_event_names = _collect_bin_events_by_keyword(bin_obj, "sfx")
    vo_event_names = _collect_bin_events_by_keyword(bin_obj, "vo")

    sfx_hirc = _parse_hirc_from_bnk(str(paths["sfx_events_bnk"]))
    vo_hirc = _parse_hirc_from_bnk(str(paths["vo_events_bnk"]))

    return {
        "champion": champion,
        "skin": entry.get("skin"),
        "files": entry.get("files", {}),
        "bin": _summarize_bin(bin_obj),
        "bnk": {
            "sfx_audio_bnk": _summarize_bnk(sfx_audio_bnk, sfx_audio_wems),
            "sfx_events_bnk": {
                **_summarize_bnk(sfx_events_bnk, sfx_events_wems),
                "hirc": _summarize_hirc(sfx_hirc),
            },
            "vo_audio_bnk": _summarize_bnk(vo_audio_bnk, vo_audio_bnk_wems),
            "vo_events_bnk": {
                **_summarize_bnk(vo_events_bnk, vo_events_wems),
                "hirc": _summarize_hirc(vo_hirc),
            },
        },
        "wpk": {
            "vo_audio_wpk": _summarize_wpk(vo_audio_wpk, vo_audio_wpk_wems),
        },
        "mapping": {
            "sfx_event_to_file_ids": _build_event_mapping_report(
                sfx_event_names, sfx_hirc, sfx_audio_ids
            ),
            "vo_event_to_file_ids": _build_event_mapping_report(
                vo_event_names, vo_hirc, vo_audio_wpk_ids
            ),
        },
    }


def _build_full_chain_report(manifest_data: dict) -> dict:
    champions = manifest_data.get("champions", [])
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_root": str(FIXTURE_ROOT),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_meta": {
            "game_root": manifest_data.get("game_root"),
            "locale": manifest_data.get("locale"),
            "skin": manifest_data.get("skin"),
            "champion_source": manifest_data.get("champion_source"),
            "champion_count": len(champions),
        },
        "champions": [_build_champion_chain_report(entry) for entry in champions],
    }


def _write_full_chain_report(report: dict) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return REPORT_PATH


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

        sfx_wems = sfx_audio_bnk.extract_files()
        vo_audio_bnk_wems = vo_audio_bnk.extract_files()
        wpk_wems = vo_audio_wpk.extract_files()

        sfx_ids = {wem.id for wem in sfx_wems if wem.id > 0}
        vo_audio_bnk_ids = {wem.id for wem in vo_audio_bnk_wems if wem.id > 0}
        wpk_ids = {wem.id for wem in wpk_wems if wem.id > 0}

        assert sfx_ids, f"{champion} sfx_audio_bnk 未解析出任何 WEM ID"
        assert wpk_ids, f"{champion} vo_audio_wpk 未解析出任何 WEM ID"
        assert vo_audio_wpk.file_count >= len(wpk_ids), f"{champion} WPK file_count 与解析ID数量异常"
        assert any(wem.data for wem in sfx_wems if wem.id > 0), f"{champion} sfx_audio_bnk 未加载到实际音频字节"
        assert any(wem.data for wem in wpk_wems if wem.id > 0), f"{champion} vo_audio_wpk 未加载到实际音频字节"

        if vo_audio_bnk_ids:
            assert vo_audio_bnk_ids.issubset(wpk_ids), f"{champion} vo_audio_bnk 的WEM ID不在WPK中"


def test_extracted_wem_payload_can_be_saved(manifest_data: dict, tmp_path: Path) -> None:
    entry = manifest_data["champions"][0]
    champion = entry["champion"]
    paths = _entry_paths(entry)

    vo_audio_wpk = _parse_wpk(str(paths["vo_audio_wpk"]))
    positive_wems = [wem for wem in vo_audio_wpk.extract_files() if wem.id > 0 and wem.data]
    assert positive_wems, f"{champion} vo_audio_wpk 未提取到可保存的 WEM 数据"

    sample = positive_wems[0]
    out_path = tmp_path / f"{champion.lower()}_{sample.id}.wem"
    sample.save_file(out_path)

    assert out_path.exists(), f"{champion} WEM 文件未成功落盘: {out_path}"
    assert out_path.stat().st_size == len(sample.data), f"{champion} WEM 落盘大小与内存数据不一致"


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


def test_generate_full_chain_report(manifest_data: dict) -> None:
    wwiser_manager = _get_wwiser_manager()
    if not wwiser_manager.wwiser_path:
        pytest.skip("未找到 wwiser.pyz，跳过完整链路报告生成")

    report = _build_full_chain_report(manifest_data)
    report_path = _write_full_chain_report(report)

    assert report_path.exists(), f"未生成完整链路报告: {report_path}"
    assert len(report["champions"]) == len(manifest_data["champions"]), "报告英雄数量与清单不一致"
