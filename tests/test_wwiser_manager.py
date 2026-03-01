from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from league_tools.utils import wwiser as wwiser_module
from league_tools.utils.wwiser import Singleton, WwiserManager


@pytest.fixture(autouse=True)
def reset_wwiser_singleton():
    Singleton._instances.pop(WwiserManager, None)
    yield
    Singleton._instances.pop(WwiserManager, None)


def _build_manager_without_discovery(monkeypatch: pytest.MonkeyPatch) -> WwiserManager:
    monkeypatch.setattr(WwiserManager, "_find_wwiser", lambda self, p: None)
    return WwiserManager(auto_download=False)


def test_expected_version_is_latest_release_tag() -> None:
    assert WwiserManager.EXPECTED_VERSION == "20250928"


def test_validate_version_match_and_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_wwiser = tmp_path / "wwiser.pyz"
    fake_wwiser.write_bytes(b"not-a-real-pyz")

    logs = {"info": [], "warning": [], "debug": [], "error": []}

    class FakeLogger:
        def info(self, msg):
            logs["info"].append(str(msg))

        def warning(self, msg):
            logs["warning"].append(str(msg))

        def debug(self, msg):
            logs["debug"].append(str(msg))

        def error(self, msg):
            logs["error"].append(str(msg))

    version_box = {"value": "20250928"}

    def fake_run(*args, **kwargs):
        stdout = f"wwiser v{version_box['value']} - Wwise .bnk parser by bnnm"
        return SimpleNamespace(stdout=stdout, stderr="")

    monkeypatch.setattr(wwiser_module, "logger", FakeLogger())
    monkeypatch.setattr(wwiser_module.subprocess, "run", fake_run)

    manager = WwiserManager(wwiser_path=str(fake_wwiser), auto_download=False)
    assert manager.get_version() == "20250928"
    assert any("版本验证通过" in msg for msg in logs["info"])
    assert not any("不匹配" in msg for msg in logs["warning"])

    logs["info"].clear()
    logs["warning"].clear()
    version_box["value"] = "20240101"
    manager._validate_version()
    assert any("不匹配" in msg for msg in logs["warning"])


def test_download_wwiser_latest_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manager = _build_manager_without_discovery(monkeypatch)

    release_info = {
        "tag_name": "v20250928",
        "assets": [
            {
                "name": "wwiser.pyz",
                "browser_download_url": "https://github.com/bnnm/wwiser/releases/download/v20250928/wwiser.pyz",
            }
        ],
    }

    class FakeHTTP:
        def __init__(self):
            self.calls: list[str] = []

        def request(self, method: str, url: str, timeout: int = 5):
            self.calls.append(url)
            if url == WwiserManager.GITHUB_API_URL:
                return SimpleNamespace(
                    status=200,
                    data=json.dumps(release_info).encode("utf-8"),
                )
            if url.endswith("/v20250928/wwiser.pyz"):
                return SimpleNamespace(status=200, data=b"WWISER-PYZ")
            return SimpleNamespace(status=404, data=b"")

    fake_http = FakeHTTP()
    monkeypatch.setattr(wwiser_module.urllib3, "PoolManager", lambda: fake_http)

    downloaded = manager.download_wwiser(output_dir=tmp_path, version="latest")
    assert downloaded == tmp_path / "wwiser.pyz"
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"WWISER-PYZ"
    assert WwiserManager.GITHUB_API_URL in fake_http.calls


def test_download_wwiser_fallback_to_expected_version_and_cdn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manager = _build_manager_without_discovery(monkeypatch)

    class FakeHTTP:
        def __init__(self):
            self.calls: list[str] = []

        def request(self, method: str, url: str, timeout: int = 5):
            self.calls.append(url)
            if url == WwiserManager.GITHUB_API_URL:
                return SimpleNamespace(status=500, data=b"")

            expected_url = (
                f"https://github.com/bnnm/wwiser/releases/download/"
                f"v{WwiserManager.EXPECTED_VERSION}/wwiser.pyz"
            )
            if url == expected_url:
                return SimpleNamespace(status=404, data=b"")

            if url == f"https://ghfast.top/{expected_url}":
                return SimpleNamespace(status=200, data=b"WWISER-CDN")

            return SimpleNamespace(status=404, data=b"")

    fake_http = FakeHTTP()
    monkeypatch.setattr(wwiser_module.urllib3, "PoolManager", lambda: fake_http)

    downloaded = manager.download_wwiser(output_dir=tmp_path, version="latest")
    assert downloaded == tmp_path / "wwiser.pyz"
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"WWISER-CDN"
    assert any(f"v{WwiserManager.EXPECTED_VERSION}/wwiser.pyz" in u for u in fake_http.calls)
    assert any(u.startswith("https://ghfast.top/https://github.com/bnnm/wwiser/releases/download/") for u in fake_http.calls)
