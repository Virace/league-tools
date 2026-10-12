from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path

import pytest

from league_tools import AudioEventMapper, NativeHIRC, WwiserHIRC


@pytest.fixture(scope="module")
def valorant_sample(request: pytest.FixtureRequest) -> tuple[dict, dict, Path]:
    root = Path(request.config.getoption("--fixture-output"))
    if not root.is_absolute():
        root = Path(request.config.rootpath) / root
    root /= "valorant"
    files = [
        root / name
        for name in ("SB_Weapons_Base.bnk", "layer.xml", "layer-reference.json")
    ]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        reason = "缺少本地 VALORANT 样本：" + ", ".join(missing)
        if request.config.getoption("--require-valorant-fixtures"):
            pytest.fail(reason)
        pytest.skip(reason)

    bnk, xml, reference_path = files
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(bnk.read_bytes()).hexdigest() == reference["bank_sha256"]
    hirc = {
        "native": NativeHIRC.from_bnk(bnk, use_cache=False),
        "wwiser": WwiserHIRC.from_xml(xml, use_cache=False),
    }
    return hirc, reference, xml


@pytest.mark.parametrize("backend", ["native", "wwiser"])
def test_valorant_layer_children_match_wwiser(
    backend: str, valorant_sample: tuple[dict, dict, Path]
) -> None:
    hirc, reference, _ = valorant_sample
    bank = next(iter(hirc[backend].banks.values()))
    actual = {
        str(identity): {
            "direct_parent_id": layer.direct_parent_id,
            "child_ids": layer.child_ids,
        }
        for identity, layer in bank.layer_containers.items()
    }
    assert actual == reference["layers"]


@pytest.mark.parametrize("backend", ["native", "wwiser"])
def test_valorant_layer_event_media_match_wwiser(
    backend: str, valorant_sample: tuple[dict, dict, Path]
) -> None:
    hirc, reference, _ = valorant_sample
    expected = reference["event_to_file_ids"]
    actual = (
        AudioEventMapper(list(expected), hirc[backend]).build_mapping().forward_mapping
    )
    assert actual == expected


def test_valorant_old_cache_reparses_layers(
    tmp_path: Path, valorant_sample: tuple[dict, dict, Path]
) -> None:
    _, reference, xml = valorant_sample
    cached = WwiserHIRC.from_xml(xml, cache_dir=tmp_path, use_cache=True)
    for bank in cached.banks.values():
        del bank.layer_containers
    cache_file = next(tmp_path.glob("*.hirc.pkl"))
    with cache_file.open("wb") as stream:
        pickle.dump(cached, stream)

    hirc = WwiserHIRC.from_xml(xml, cache_dir=tmp_path, use_cache=True)
    bank = next(iter(hirc.banks.values()))
    assert sorted(bank.layer_containers) == sorted(map(int, reference["layers"]))
