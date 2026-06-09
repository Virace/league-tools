from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


WORKTREE_REF = "WORKTREE"


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dependency_name(dependency: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", dependency)
    if match is None:
        return dependency
    return _normalize_name(match.group(1))


def _dependency_map(dependencies: Iterable[str]) -> dict[str, str]:
    return {_dependency_name(dependency): dependency for dependency in dependencies}


def _lock_versions(lock: dict[str, object]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in lock.get("package", []):
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        version = package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            versions[_normalize_name(name)] = version
    return versions


def _display_name(
    name: str,
    old_dependencies: dict[str, str],
    new_dependencies: dict[str, str],
) -> str:
    dependency = new_dependencies.get(name) or old_dependencies.get(name)
    if dependency is None:
        return name
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", dependency)
    return match.group(1) if match is not None else name


def _display_requirement(dependency: str) -> str:
    requirement = re.sub(r"^\s*[A-Za-z0-9_.-]+(?:\[[^\]]+\])?\s*", "", dependency)
    return requirement or dependency


def _dependency_lines(
    old_dependencies: dict[str, str],
    new_dependencies: dict[str, str],
    old_versions: dict[str, str],
    new_versions: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    for name in sorted(set(old_dependencies) | set(new_dependencies)):
        old_spec = old_dependencies.get(name)
        new_spec = new_dependencies.get(name)
        old_version = old_versions.get(name)
        new_version = new_versions.get(name)
        if old_spec == new_spec and old_version == new_version:
            continue

        display_name = _display_name(name, old_dependencies, new_dependencies)
        if old_spec is None:
            line = f"- `{display_name}`: added `{_display_requirement(new_spec or '')}`"
        elif new_spec is None:
            line = f"- `{display_name}`: removed `{_display_requirement(old_spec)}`"
        else:
            line = (
                f"- `{display_name}`: `{_display_requirement(old_spec)}`"
                f" -> `{_display_requirement(new_spec)}`"
            )

        if (
            old_version != new_version
            and old_version is not None
            and new_version is not None
        ):
            line = f"{line} (locked `{old_version}` -> `{new_version}`)"
        lines.append(line)
    return lines


def build_release_notes(
    old_pyproject: dict[str, object],
    old_lock: dict[str, object],
    new_pyproject: dict[str, object],
    new_lock: dict[str, object],
) -> str:
    old_runtime = _dependency_map(
        old_pyproject.get("project", {}).get("dependencies", [])
    )
    new_runtime = _dependency_map(
        new_pyproject.get("project", {}).get("dependencies", [])
    )
    old_dev = _dependency_map(old_pyproject.get("dependency-groups", {}).get("dev", []))
    new_dev = _dependency_map(new_pyproject.get("dependency-groups", {}).get("dev", []))
    old_versions = _lock_versions(old_lock)
    new_versions = _lock_versions(new_lock)

    runtime_lines = _dependency_lines(
        old_runtime, new_runtime, old_versions, new_versions
    )
    dev_lines = _dependency_lines(old_dev, new_dev, old_versions, new_versions)
    direct_dependencies = (
        set(old_runtime) | set(new_runtime) | set(old_dev) | set(new_dev)
    )
    project_name = _normalize_name(
        str(new_pyproject.get("project", {}).get("name", ""))
    )

    lock_only_lines: list[str] = []
    for name in sorted(set(old_versions) | set(new_versions)):
        if name in direct_dependencies or name == project_name:
            continue
        old_version = old_versions.get(name)
        new_version = new_versions.get(name)
        if (
            old_version != new_version
            and old_version is not None
            and new_version is not None
        ):
            lock_only_lines.append(f"- `{name}`: `{old_version}` -> `{new_version}`")

    sections: list[str] = ["## 依赖更新", ""]
    if runtime_lines:
        sections.extend(["### Runtime dependencies", *runtime_lines, ""])
    if dev_lines:
        sections.extend(["### Development dependencies", *dev_lines, ""])
    if lock_only_lines:
        sections.extend(["### Lockfile-only dependency updates", *lock_only_lines, ""])

    if sections == ["## 依赖更新", ""]:
        sections.append("No dependency changes detected.")

    return "\n".join(sections).rstrip() + "\n"


def _read_ref_file(ref: str, path: str) -> str:
    if ref == WORKTREE_REF:
        return Path(path).read_text(encoding="utf-8")
    return subprocess.check_output(
        ["git", "show", f"{ref}:{path}"],
        encoding="utf-8",
        text=True,
    )


def _load_toml(ref: str, path: str) -> dict[str, object]:
    return tomllib.loads(_read_ref_file(ref, path))


def generate_release_notes(old_ref: str, new_ref: str) -> str:
    return build_release_notes(
        _load_toml(old_ref, "pyproject.toml"),
        _load_toml(old_ref, "uv.lock"),
        _load_toml(new_ref, "pyproject.toml"),
        _load_toml(new_ref, "uv.lock"),
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-ref", required=True)
    parser.add_argument("--new-ref", default=WORKTREE_REF)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(list(argv) if argv is not None else None)

    notes = generate_release_notes(args.old_ref, args.new_ref)
    if args.output == "-":
        print(notes, end="")
    else:
        Path(args.output).write_text(notes, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
