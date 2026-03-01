from __future__ import annotations

from league_tools.formats.bnk.section.HIRC import Action, Event, RanSeqCntr, Sound, SwitchCntr
from league_tools.formats.bnk.wwiser import WwiserBank, WwiserHIRC
from league_tools.tools.audio_mapper import AudioEventMapper, AudioMapping, MappingAnalyzer
from league_tools.utils.hash import str_fnv_32


def _build_hirc_graph() -> tuple[WwiserHIRC, str, str]:
    hirc = WwiserHIRC(use_cache=False)
    bank = WwiserBank(filename="unit_test_events.bnk")

    event_attack = "Play_vo_Test_Attack"
    event_move = "Play_vo_Test_Move"

    attack_id = str_fnv_32(event_attack)
    move_id = str_fnv_32(event_move)

    bank.events[attack_id] = Event(object_id=attack_id, event_ids=[2001])
    bank.events[move_id] = Event(object_id=move_id, event_ids=[2002])

    bank.event_actions[2001] = Action(
        object_id=2001,
        action_type=0,
        id_ext=3001,
        switch_group_id=0,
        switch_state_id=0,
        state_group_id=0,
        target_state_id=0,
    )
    bank.event_actions[2002] = Action(
        object_id=2002,
        action_type=0,
        id_ext=3002,
        switch_group_id=0,
        switch_state_id=0,
        state_group_id=0,
        target_state_id=0,
    )

    # random_container 包含自引用，验证 BFS 的 visited 去重不会死循环
    bank.random_containers[3001] = RanSeqCntr(
        object_id=3001, direct_parent_id=0, child_ids=[4001, 4002, 3001]
    )
    bank.switch_containers[3002] = SwitchCntr(
        object_id=3002, direct_parent_id=0, child_ids=[4003, 4001]
    )

    # source_id=0 应被过滤，不进入最终映射
    bank.sounds[4001] = Sound(object_id=4001, source_id=90001, stream_type=0)
    bank.sounds[4002] = Sound(object_id=4002, source_id=0, stream_type=0)
    bank.sounds[4003] = Sound(object_id=4003, source_id=90002, stream_type=0)

    hirc.add_bank(bank)
    return hirc, event_attack, event_move


def test_audio_event_mapper_build_mapping_from_event_names() -> None:
    hirc, event_attack, event_move = _build_hirc_graph()
    unknown_event = "Play_vo_Test_Unknown"

    mapper = AudioEventMapper([event_attack, event_move, unknown_event], hirc)
    mapping = mapper.build_mapping()

    assert mapping.find_sounds_by_event_name(event_attack) == [90001]
    assert mapping.find_sounds_by_event_name(event_move) == [90001, 90002]
    assert mapping.find_sounds_by_event_name(unknown_event) == []
    assert mapping.find_events_by_sound_id(90001) == [event_attack, event_move]
    assert mapping.find_events_by_sound_id(90002) == [event_move]
    assert not mapping.has_sound_id(0)
    assert not mapping.has_event_name(unknown_event)


def test_audio_mapping_merge_and_serialization_order() -> None:
    mapping_a = AudioMapping(
        forward_mapping={"event_b": [2, 1], "event_a": [3]},
        reverse_mapping={},
    )
    mapping_b = AudioMapping(
        forward_mapping={"event_a": [3, 4], "event_c": [1]},
        reverse_mapping={},
    )

    merged = mapping_a.merge_with(mapping_b)
    data = merged.to_dict()

    assert merged.find_sounds_by_event_name("event_a") == [3, 4]
    assert merged.find_sounds_by_event_name("event_b") == [1, 2]
    assert list(data["forward_mapping"].keys()) == ["event_a", "event_b", "event_c"]
    assert list(data["reverse_mapping"].keys()) == ["1", "2", "3", "4"]


def test_mapping_analyzer_outputs_expected_metrics() -> None:
    mapping = AudioMapping(
        forward_mapping={
            "event_1": [1001, 1002],
            "event_2": [1002],
        },
        reverse_mapping={},
    )
    analyzer = MappingAnalyzer(mapping)

    coverage = analyzer.analyze_file_coverage(["1001", "1002", "1003"])
    complexity = analyzer.analyze_event_complexity()
    reuse = analyzer.analyze_sound_reuse()
    report = analyzer.get_comprehensive_analysis(actual_files=["1001", "1003"])

    assert coverage["categorized_count"] == 2
    assert coverage["uncategorized_files"] == [1003]
    assert coverage["mapping_not_exist"] == []
    assert coverage["coverage_rate"] == 66.67

    assert complexity["total_events"] == 2
    assert complexity["simple_events"] == 1
    assert complexity["complex_events"] == 1

    assert reuse["total_sounds"] == 2
    assert reuse["unique_sounds"] == 1
    assert reuse["reused_sounds"] == 1

    assert "mapping_stats" in report
    assert "file_coverage" in report
