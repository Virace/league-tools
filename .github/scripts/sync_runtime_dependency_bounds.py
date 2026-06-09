from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


DEPENDENCY_LINE_RE = re.compile(
    r'(?P<prefix>\s*")'
    r"(?P<name>[A-Za-z0-9_.-]+)"
    r"(?P<specifier>>=)"
    r'(?P<version>[^",\s]+)'
    r"(?P<suffix>.*)$"
)
SECTION_RE = re.compile(r"^\[(?P<section>[A-Za-z0-9_.-]+)]\s*$")


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _version_key(version: str) -> tuple[int | str, ...]:
    parts: list[int | str] = []
    for part in re.split(r"[.+-]", version):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return tuple(parts)


def _locked_versions(lock_path: Path) -> dict[str, str]:
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    for package in data.get("package", []):
        name = package.get("name")
        version = package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            versions[_normalize_name(name)] = version
    return versions


def sync_runtime_bounds(pyproject_path: Path, lock_path: Path) -> list[str]:
    lines = pyproject_path.read_text(encoding="utf-8").splitlines(keepends=True)
    locked = _locked_versions(lock_path)
    changed: list[str] = []
    output_lines: list[str] = []
    section: str | None = None
    in_project_dependencies = False

    for line in lines:
        stripped = line.strip()
        section_match = SECTION_RE.match(stripped)
        if section_match:
            section = section_match.group("section")
            in_project_dependencies = False

        if section == "project" and re.match(r"^dependencies\s*=\s*\[$", stripped):
            in_project_dependencies = True
            output_lines.append(line)
            continue

        if in_project_dependencies and stripped == "]":
            in_project_dependencies = False
            output_lines.append(line)
            continue

        if not in_project_dependencies:
            output_lines.append(line)
            continue

        newline = "\n" if line.endswith("\n") else ""
        content = line[:-1] if newline else line
        match = DEPENDENCY_LINE_RE.match(content)
        if not match:
            output_lines.append(line)
            continue

        raw_name = match.group("name")
        normalized = _normalize_name(raw_name)
        current_version = match.group("version")
        locked_version = locked.get(normalized)

        if locked_version is not None and _version_key(locked_version) > _version_key(
            current_version
        ):
            output_lines.append(
                f"{match.group('prefix')}{raw_name}>={locked_version}{match.group('suffix')}{newline}"
            )
            changed.append(f"{raw_name}: {current_version} -> {locked_version}")
        else:
            output_lines.append(line)

    if changed:
        pyproject_path.write_text("".join(output_lines), encoding="utf-8", newline="\n")

    return changed


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--lock", default="uv.lock")
    args = parser.parse_args(list(argv) if argv is not None else None)

    changed = sync_runtime_bounds(Path(args.pyproject), Path(args.lock))
    for item in changed:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
