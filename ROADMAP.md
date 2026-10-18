# FoamKit Roadmap

## Decisions (2026-10-18)
- **Approved by maintainer:** the ranked order below, the T-010 canonical name table and the `case.canonical(...)` accessor.
- **T-013 unit API:** parsed units go on a new `.units` attribute. Unit-annotated values come back typed instead of as strings; this is treated as a bug fix and gets a CHANGELOG note.
- **Docs:**
  - Sphinx + MyST + Furo; the strict build is `sphinx-build -W --keep-going -b html docs docs/_build/html`.
  - Doc and README examples use `import foamkit.functions as fkf` / `import foamkit.types as fkt`.
- **Checks:** `mypy foamkit/`. ruff and mypy are not installed yet, so for now tickets check "no new findings compared with today" (T-002).
- **Python:** 3.9+, verified on 3.9.23 and 3.14; CI tests 3.9 and 3.12.
- **Release tags:** `v` prefix. Commitizen `tag_format = "v$version"` already matches; only the README needs fixing (T-003).
- **OpenFOAM support:**
  - Tested: Foundation 11-14 and ESI v2412, v2506, v2512, v2606.
  - Older releases are best-effort.
  - Detection order: override, then case banner, then environment.
  - Canonical names follow Foundation 14, mapped through one data table; writes keep the case's native names.
- **`bin/` scripts:** deleted by the maintainer (staged).

## Current state
- The core init → cache → load → edit → write path is tested (99 passed, 1 skipped) on Linux and Windows CI.
- Verified bugs that lose data:
  - `#sinclude`/`#includeIfPresent` are rewritten as `#include`;
  - boxed-banner and bannerless files are silently dropped;
  - unit-annotated values (Foundation 13+) are corrupted or fail to parse.
- There is no docs site, the README has broken examples, and lint and type checks are not runnable.

## Next (ranked)
1. **T-002** ruff + mypy baseline (S): every code ticket below cites these checks.
2. **T-004** keep include directives intact (S): silent case corruption.
3. **T-005** recognise boxed and bannerless files (S): files silently missing from cases.
4. **T-013** unit-annotated values (M): Foundation 13/14 inputs corrupt or fail to parse; this hits half the tested Foundation releases.
5. **T-003** README corrections (S): the PyPI page has code that does not run.
6. **T-001** Sphinx site + Quickstart (M): verified entry point; T-012 depends on it.
7. **T-006** preserve headers on write (S): finishes making read and write lossless.

After these, the order is T-007 → T-008 → T-010 → T-009 → T-011 → T-012 → T-014 (see `docs/plans/openfoam-compatibility.md`).

## Deferred
- **API reference:** after T-010 stabilises the API. Use autodoc2 or an env-clean autodoc (see T-001 risks).
- **Repo-wide `ruff format`, lint in CI:** after T-002.
- **Console aliases `pf`/`pt` → `fkf`/`fkt`:** a code ticket with a deprecation path, after T-003.
- **Real-OpenFOAM CI, write-side canonical helpers, case conversion, tutorials, hosting, versioned docs:** these need the work above first.
