from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("league-tools")
    group.addoption(
        "--prepare-fixtures",
        action="store_true",
        default=False,
        help="在测试开始前自动提取测试样本",
    )
    group.addoption(
        "--fixture-game-root",
        action="store",
        default=os.environ.get("LEAGUE_TOOLS_GAME_ROOT", ""),
        help="Champions WAD 目录（可由 LEAGUE_TOOLS_GAME_ROOT 提供）",
    )
    group.addoption(
        "--fixture-output",
        action="store",
        default="tests/fixtures/external",
        help="测试样本输出目录",
    )
    group.addoption(
        "--fixture-locale",
        action="store",
        default=os.environ.get("LEAGUE_TOOLS_FIXTURE_LOCALE", "zh_CN"),
        help="样本区域（默认 zh_CN）",
    )
    group.addoption(
        "--fixture-skin",
        action="store",
        type=int,
        default=int(os.environ.get("LEAGUE_TOOLS_FIXTURE_SKIN", "1")),
        help="皮肤编号（默认 1）",
    )
    group.addoption(
        "--fixture-sample-size",
        action="store",
        type=int,
        default=int(os.environ.get("LEAGUE_TOOLS_FIXTURE_SAMPLE_SIZE", "5")),
        help="抽样英雄数量（默认 5）",
    )
    group.addoption(
        "--fixture-seed",
        action="store",
        default=os.environ.get("LEAGUE_TOOLS_FIXTURE_SEED", None),
        help="随机种子（可选）",
    )
    group.addoption(
        "--fixture-no-xml",
        action="store_true",
        default=False,
        help="不生成 XML",
    )
    group.addoption(
        "--fixture-include-root-bin",
        action="store_true",
        default=False,
        help="提取 root.bin",
    )
    group.addoption(
        "--fixture-no-clean",
        action="store_true",
        default=False,
        help="不清空样本输出目录",
    )
    group.addoption(
        "--fixture-no-auto-download-wwiser",
        action="store_true",
        default=False,
        help="禁用自动下载 wwiser",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    config = session.config
    if not config.getoption("--prepare-fixtures"):
        return

    game_root = config.getoption("--fixture-game-root")
    if not game_root:
        pytest.exit(
            "缺少 --fixture-game-root（或环境变量 LEAGUE_TOOLS_GAME_ROOT）。",
            returncode=2,
        )

    repo_root = Path(config.rootpath)
    script_path = repo_root / "scripts" / "extract_wad_fixtures.py"
    if not script_path.exists():
        pytest.exit(f"未找到样本提取脚本: {script_path}", returncode=2)

    cmd = [
        sys.executable,
        str(script_path),
        "--game-root",
        str(game_root),
        "--output",
        str(config.getoption("--fixture-output")),
        "--locale",
        str(config.getoption("--fixture-locale")),
        "--skin",
        str(config.getoption("--fixture-skin")),
        "--sample-size",
        str(config.getoption("--fixture-sample-size")),
    ]

    seed = config.getoption("--fixture-seed")
    if seed is not None and str(seed).strip():
        cmd.extend(["--seed", str(seed)])

    if config.getoption("--fixture-no-xml"):
        cmd.append("--no-generate-xml")
    if config.getoption("--fixture-include-root-bin"):
        cmd.append("--include-root-bin")
    if config.getoption("--fixture-no-clean"):
        cmd.append("--no-clean")
    if config.getoption("--fixture-no-auto-download-wwiser"):
        cmd.append("--no-auto-download-wwiser")

    try:
        subprocess.run(cmd, check=True, cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        pytest.exit(f"样本提取失败，退出码 {exc.returncode}", returncode=exc.returncode)
