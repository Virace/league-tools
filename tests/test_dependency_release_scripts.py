from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> ModuleType:
    path = ROOT / ".github" / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_runtime_dependency_bounds_only_updates_project_dependencies(
    tmp_path: Path,
) -> None:
    script = _load_script("sync_runtime_dependency_bounds.py")
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "uv.lock"

    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                'version = "1.2.3"',
                "dependencies = [",
                '    "urllib3>=2.6.3",',
                '    "pytest>=9.0.2",',
                "]",
                "",
                "[dependency-groups]",
                "dev = [",
                '    "pygments>=2.19.2",',
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lock.write_text(
        "\n".join(
            [
                "version = 1",
                "revision = 3",
                "",
                "[[package]]",
                'name = "urllib3"',
                'version = "2.7.0"',
                "",
                "[[package]]",
                'name = "pytest"',
                'version = "9.0.3"',
                "",
                "[[package]]",
                'name = "pygments"',
                'version = "2.20.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    changed = script.sync_runtime_bounds(pyproject, lock)

    assert changed == ["urllib3: 2.6.3 -> 2.7.0", "pytest: 9.0.2 -> 9.0.3"]
    text = pyproject.read_text(encoding="utf-8")
    assert '"urllib3>=2.7.0",' in text
    assert '"pytest>=9.0.3",' in text
    assert '"pygments>=2.19.2",' in text


def test_sync_runtime_dependency_bounds_ignores_dev_dependency_with_same_locked_update(
    tmp_path: Path,
) -> None:
    script = _load_script("sync_runtime_dependency_bounds.py")
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "uv.lock"

    pyproject.write_text(
        "\n".join(
            [
                "[project]",
                'version = "1.2.3"',
                'dependencies = ["urllib3>=2.6.3"]',
                "",
                "[dependency-groups]",
                "dev = [",
                '    "pytest>=9.0.2",',
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lock.write_text(
        "\n".join(
            [
                "version = 1",
                "revision = 3",
                "",
                "[[package]]",
                'name = "urllib3"',
                'version = "2.7.0"',
                "",
                "[[package]]",
                'name = "pytest"',
                'version = "9.0.3"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    changed = script.sync_runtime_bounds(pyproject, lock)

    assert changed == []
    text = pyproject.read_text(encoding="utf-8")
    assert '"pytest>=9.0.2",' in text


def test_bump_patch_version(tmp_path: Path) -> None:
    script = _load_script("bump_patch_version.py")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    new_version = script.bump_patch(pyproject)

    assert new_version == "1.2.4"
    assert 'version = "1.2.4"' in pyproject.read_text(encoding="utf-8")
