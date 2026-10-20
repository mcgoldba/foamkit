# T-007: Per-release fixture cases and parametrized round-trip tests

- **Issue:** [#14](https://github.com/mcgoldba/foamkit/issues/14)
- **Type:** code, tests only (owner: `tester`; `implementer` only for the `pyproject.toml` marker registration)
- **Size:** M
- **Plan:** docs/plans/openfoam-compatibility.md, section 3
- **Depends on:** T-004, T-005, T-006, T-013, T-015, T-016, T-019, T-021, T-022. T-020 is **not** a dependency: remaining entry padding/layout differences are marked `xfail(strict=True, reason="T-020")`, and these fixtures become T-020's test corpus.

## Goal
CI demonstrates, without OpenFOAM installed, that FoamKit reads, edits and writes representative cases from each **tested** release.

**Note (2026-10-19, real files):** stock pitzDaily for **Foundation 11** cannot load until T-015 lands (`#includeFunc patchAverage(...)` in `controlDict`), and for **Foundation 14** until T-016 lands (`#print` in `momentumTransport`). The pitzDaily fixture set for 11 and 14 therefore depends on T-015 and T-016. Foundation pitzDaily lives at `tutorials/incompressibleFluid/pitzDaily/` in releases 11-14.

## Tested matrix (maintainer decision, 2026-10-18: the four latest releases of each distribution)
- **Foundation:** 11, 12, 13, 14
- **ESI:** v2412, v2506, v2512, v2606

Older releases (Foundation 7-10, ESI v2006-v2406) are **best-effort and untested**. They get no fixture here.

**foam-extend (optional, later):** full `foam-extend-4.1` / `foam-extend-5.0` case fixtures may be added in a follow-up. The header-level fixtures in `tests/fixtures/headers/` (T-005, T-006) already cover their banners. Fetch sources from SourceForge (plan References).

## Scope
- `tests/fixtures/releases/{foundation-11,foundation-12,foundation-13,foundation-14,esi-v2412,esi-v2506,esi-v2512,esi-v2606}/`. Each is a minimal case with:
  - `system/controlDict`, `fvSchemes`, `fvSolution`;
  - the release's turbulence and physical-properties files;
  - one `0/` (or `0.orig/`) field.

  The files are fetched byte-exact (`curl -sfL`, URLs in the plan's References section) from that release's `pitzDaily` (or the closest incompressible tutorial) and trimmed, keeping the real banners, include directives and (Foundation 13/14) unit-annotated values. LF line endings, as enforced by `.gitattributes`.
- `tests/fixtures/releases/README.md`: the source release, tutorial path and download date for each fixture.
- A **fact-check table** in that README. For each family, record the actual file and key names found: turbulence file, RAS model key, physical-properties file, fvModels/fvConstraints/fvOptions, `application`/`solver`, banner style, residuals function object name. The plan's version-specific claims were written from memory; this table replaces them, and T-010 and T-012 use it as their source.
- `tests/test_releases.py`, parametrized over the families:
  - all dictionary files are present in `pf.init(...)`;
  - init → save → load → write is byte-identical for unedited files;
  - one `controlDict.endTime` edit lands correctly.
- `pyproject.toml`: register `markers = ["openfoam: needs a real OpenFOAM install"]`, and deselect the marker by default or skip when `WM_PROJECT_DIR` is unset.

## Out of scope
- Detection or alias code (T-008, T-010)
- Real OpenFOAM tests in CI (deferred)
- Fixtures for best-effort releases

## Acceptance criteria
- [ ] Eight fixture families exist, each under 30 KB, and each source is recorded.
- [ ] The fact-check table is filled in for all eight families.
- [ ] `pytest -q` passes on 3.9 and 3.12 in CI. Any remaining gap is a test marked `xfail(strict=True)` with a reason, and a follow-up ticket is listed here.
- [ ] `pytest --markers` lists `openfoam`, and no `openfoam`-marked test runs without an install.
- [ ] No change under `foamkit/`.
- [ ] Any plan statement contradicted by the fact-check table is reported back for a plan update.

## Risks
- **Licence:** OpenFOAM is GPLv3, and so is FoamKit. Keep the original copyright headers.
- **Getting real files:** the tester needs the release sources or containers. Downloading tutorial files from the official repositories is enough; no install is needed.
- **The tested set moves:** "four latest" changes with each release. The update rule is to add the new release and drop the oldest; it is recorded in T-012.
