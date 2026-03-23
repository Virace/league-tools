from __future__ import annotations

from pathlib import Path

from league_tools import AudioEventMapper, NativeHIRC, WwiserHIRC
from league_tools.utils.wwiser import WwiserManager


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "music_switch"
MUS_MAP11ARCADE_EVENTS_BNK = FIXTURE_ROOT / "MUS_Map11Arcade_events.bnk"
MUS_MAP11ARCADE_EVENTS = [
    "Play_mus_map11_phase_defeat_Arcade",
    "Play_mus_map11_phase_select_Arcade",
    "Play_mus_map11_phase_select_Arcade_transition",
    "Play_mus_map11_phase_victory_Arcade",
]
MUS_MAP11ARCADE_EXPECTED_MAPPING = {
    "Play_mus_map11_phase_defeat_Arcade": [419586192],
    "Play_mus_map11_phase_select_Arcade": [
        128820562,
        228073295,
        293396007,
        403862142,
        434740873,
        549272032,
        689724454,
        801502607,
    ],
    "Play_mus_map11_phase_select_Arcade_transition": [],
    "Play_mus_map11_phase_victory_Arcade": [318623636],
}


def _get_wwiser_manager() -> WwiserManager:
    return WwiserManager(auto_download=False)


def _copy_music_switch_fixture(tmp_path: Path) -> Path:
    target = tmp_path / MUS_MAP11ARCADE_EVENTS_BNK.name
    target.write_bytes(MUS_MAP11ARCADE_EVENTS_BNK.read_bytes())
    return target


def test_native_hirc_maps_real_music_switch_fixture(tmp_path: Path) -> None:
    bnk_path = _copy_music_switch_fixture(tmp_path)
    hirc = NativeHIRC.from_bnk(bnk_path, use_cache=False)

    mapping = AudioEventMapper(MUS_MAP11ARCADE_EVENTS, hirc).build_mapping()

    for event_name, expected_ids in MUS_MAP11ARCADE_EXPECTED_MAPPING.items():
        assert mapping.find_sounds_by_event_name(event_name) == expected_ids


def test_wwiser_hirc_maps_real_music_switch_fixture(tmp_path: Path) -> None:
    bnk_path = _copy_music_switch_fixture(tmp_path)
    hirc = WwiserHIRC.from_bnk(
        bnk_path,
        wwiser_manager=_get_wwiser_manager(),
        use_cache=False,
    )

    mapping = AudioEventMapper(MUS_MAP11ARCADE_EVENTS, hirc).build_mapping()

    for event_name, expected_ids in MUS_MAP11ARCADE_EXPECTED_MAPPING.items():
        assert mapping.find_sounds_by_event_name(event_name) == expected_ids
