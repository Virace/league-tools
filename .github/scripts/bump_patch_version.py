from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable


VERSION_RE = re.compile(
    r'(?m)^version = "(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"$'
)


def bump_patch(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        raise ValueError("pyproject.toml does not contain a simple X.Y.Z version")

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch")) + 1
    new_version = f"{major}.{minor}.{patch}"
    updated = VERSION_RE.sub(f'version = "{new_version}"', text, count=1)
    pyproject_path.write_text(updated, encoding="utf-8", newline="\n")
    return new_version


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", default="pyproject.toml")
    args = parser.parse_args(list(argv) if argv is not None else None)

    print(bump_patch(Path(args.pyproject)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
