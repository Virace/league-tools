from __future__ import annotations

import subprocess
import sys

from league_tools import disable_logging, enable_logging, is_logging_enabled


def _run_python_inline(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )


def test_package_import_disables_default_loguru_sink() -> None:
    result = _run_python_inline(
        "from league_tools.utils.wwiser import WwiserManager;"
        "WwiserManager(auto_download=False)"
    )
    assert "未找到wwiser.pyz" not in result.stderr


def test_enable_logging_can_manually_open_output() -> None:
    result = _run_python_inline(
        "from league_tools import enable_logging;"
        "from league_tools.utils.wwiser import WwiserManager;"
        "enable_logging();"
        "WwiserManager(auto_download=False)"
    )
    assert "league_tools.utils.wwiser" in result.stderr


def test_enable_and_disable_logging_state() -> None:
    disable_logging()
    assert not is_logging_enabled()

    enable_logging()
    assert is_logging_enabled()

    disable_logging()
    assert not is_logging_enabled()
