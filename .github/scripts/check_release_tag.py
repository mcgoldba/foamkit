"""Refuse to publish a release tag that would ship the wrong version or CHANGELOG.

Run by `.github/workflows/release.yml` on a `v*` tag push (docs/releasing.md):

1. the tag equals the `pyproject.toml` version;
2. the tagged commit is on `main` (not the pre-squash bump-branch commit);
3. every `feat`/`fix`/`refactor`/`perf`/breaking commit since the previous tag
   appears in `CHANGELOG.md`. This catches a PR that merged while the bump PR
   was open, which commitizen never saw.

Usage: python check_release_tag.py <tag> [main-ref]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    sys.exit("check_release_tag.py needs Python 3.11+ (tomllib)")

# Commit types commitizen's conventional-commits changelog lists
_LISTED = re.compile(
    r"^(?:(?:feat|fix|refactor|perf)(?:\([^)]*\))?!?|\w+(?:\([^)]*\))?!): (?P<desc>.+)$"
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def check(tag: str, main_ref: str, root: Path) -> list[str]:
    """Return one message per problem; an empty list means the tag can be published."""
    problems = []
    with open(root / "pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    if tag != f"v{version}":
        problems.append(
            f"Tag {tag} does not match pyproject.toml version {version}: merge the bump PR first and tag that commit"
        )

    on_main = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", main_ref], capture_output=True
    )
    if on_main.returncode != 0:
        problems.append(
            f"Tag {tag} is not on {main_ref}: tag the squash-merged bump commit on main"
        )

    previous = _git("describe", "--tags", "--abbrev=0", "--match", "v*", "HEAD^")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    for subject in _git("log", "--format=%s", f"{previous}..HEAD").splitlines():
        match = _LISTED.match(subject)
        if match and match.group("desc") not in changelog:
            problems.append(
                f"CHANGELOG.md has no entry for {subject!r} (merged after the bump was prepared?): "
                "re-run the bump on up-to-date main"
            )
    return problems


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    tag = sys.argv[1]
    main_ref = sys.argv[2] if len(sys.argv) == 3 else "origin/main"
    problems = check(tag, main_ref, Path(_git("rev-parse", "--show-toplevel")))
    if problems:
        sys.exit("\n".join(problems))
    print(f"{tag}: version, branch and CHANGELOG checks passed")


if __name__ == "__main__":
    main()
