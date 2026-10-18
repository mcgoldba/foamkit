# T-001: Docs site skeleton (Sphinx + MyST, strict build) and Quickstart page

- **Type:** docs (owner: `docs-writer`; `implementer` for the pyproject, environment and CI changes)
- **Size:** M
- **Workflow note:** No logic changes, so skip the tester-first step. The docs-writer adds one doc-example test under `tests/docs/`, and that test is the verification.

## Goal
A contributor can run one command on a clean checkout and get a docs site with a Quickstart page. The build runs in strict mode and passes. The Quickstart shows how to install FoamKit and load, edit and write a case, and its example has been run.

## Decision (maintainer, 2026-10-18)
The docs tool is **Sphinx + MyST-Parser (Markdown pages) + the Furo theme**. The maintainer chose it because long-term support matters more than ease of setup.

Strict build command (use this exact command everywhere: CLAUDE.md-style docs, CI, acceptance):

```
sphinx-build -W --keep-going -b html docs docs/_build/html
```

`docs/_build/` is already in `.gitignore` (line 74).

## Scope
- `docs/conf.py`:
  - extensions `myst_parser`, theme `furo`, `source_suffix` for `.md`;
  - `exclude_patterns = ["_build", "tickets", "plans"]`, so that the planning files under `docs/tickets/` and `docs/plans/` do not trigger "not in any toctree" warnings under `-W`;
  - no autodoc yet.
- `docs/index.md`: a short landing page (what FoamKit is) with a toctree containing only `quickstart`.
- `docs/quickstart.md`:
  - Install: `python -m pip install foamkit`, plus the conda dev env (`mamba env create -f environment.yml`).
  - A minimal Python example that loads, edits and writes a case. It uses the maintainer-chosen module aliases `import foamkit.functions as fkf` / `import foamkit.types as fkt` (not `pf`/`pt`) and only API proven by `tests/test_case.py`: `fkf.init(path=...)`, attribute access such as `case.system.controlDict.endTime`, assignment, `case.save(...)` / `case.write()`. It runs against a copy of `tests/fixtures/pitzDaily` and does not need OpenFOAM.
  - A CLI section that uses `fk` only (`fk init`, `fk edit`). Mention once that `pf` is a deprecated alias. Note that the `fk edit` console currently pre-imports the modules as `pf`/`pt` (`foamkit/commandline/_iPython_env.py:4-5`), so console snippets must use those names until a code ticket changes it. Label any step that needs an OpenFOAM install or an interactive console (for example `cp $FOAM_TUTORIALS/...`, `fk edit`, `case.run()`) as "requires OpenFOAM" or "interactive".
- `tests/docs/test_quickstart.py`: copies the fixture case to `tmp_path` and runs the Quickstart Python example. Keep it in sync with the page, either by extracting the fenced block or by having the page include a shared snippet file (MyST `{literalinclude}`).
- `pyproject.toml`: add a `docs` optional extra: `sphinx`, `myst-parser`, `furo`. Do not add these to `dependencies`.
- `environment.yml`: add the same three packages from conda-forge.
- `.github/workflows/release.yml`: add an independent `docs` job (ubuntu, Python 3.12) that installs `.[docs]` and runs the strict build command. It must **not** be added to `publish.needs`.

## Out of scope (later tickets)
- API reference (autodoc/autodoc2) and docstring cleanup
- Tutorials, how-to guides, explanation pages, and the Supported versions page (T-012)
- Hosting/deployment (GitHub Pages, Read the Docs), custom domain
- Versioned docs
- README changes (T-003)
- Any change to `foamkit/` source, including docstrings
- Theme customization, logos, badges

## Acceptance criteria
- [ ] On a clean checkout, after `python -m pip install -e ".[docs]"`, `sphinx-build -W --keep-going -b html docs docs/_build/html` exits 0, both on Windows (conda env) and in CI.
- [ ] `git status` is clean after a build.
- [ ] Only `index` and `quickstart` are built. `docs/tickets/**` and `docs/plans/**` are excluded and produce no warnings.
- [ ] The Quickstart Python example is run by `tests/docs/test_quickstart.py`, and that test passes without OpenFOAM (`WM_PROJECT_VERSION` unset).
- [ ] Every non-executed snippet is labelled "requires OpenFOAM" or "interactive".
- [ ] `pf` appears only in the CLI deprecation note and the `fk edit` console-alias note. `grep -nw pf docs/index.md docs/quickstart.md` shows only those lines. Script examples use `fkf`/`fkt`.
- [ ] Docs packages appear only in the `docs` extra and in `environment.yml`. `[project].dependencies` is unchanged.
- [ ] `git diff --stat -- foamkit/` is empty.
- [ ] `pytest -q` passes (baseline: 99 passed, 1 skipped, plus the new docs test).
- [ ] `ruff check . && ruff format --check .` and `mypy foamkit/` show no new findings compared with today. If T-002 has not landed yet, record "not runnable" for these two checks.
- [ ] The CI `docs` job passes on the PR, and `publish` still depends only on `test` and `build`.

## Risks
- **Future API reference:** autodoc imports `foamkit`. `foamkit/__init__.py` reads `WM_PROJECT_VERSION` and config at import (lines 15-18), and `foamkit/types/__init__.py:370-374` bakes the result into header defaults. So the generated reference could depend on the environment it was built in. When reference docs are ticketed, prefer `sphinx-autodoc2`, which analyses the code statically without importing it, or run autodoc with a clean environment. Note that autodoc2 releases less often than core Sphinx.
- **Sphinx and Python versions:** recent Sphinx needs Python 3.11 or newer, while the package supports 3.9. Run the docs job on 3.12 only. Do not add docs dependencies to the 3.9 test matrix.
- **Example drift:** a hand-copied example can drift away from the test that runs it. Fix: a single source, via `literalinclude` or block extraction.
- **OpenFOAM versions:** the fixture uses `constant/momentumTransport` (Foundation 8+). The Quickstart must not suggest that this path applies to ESI. Either keep the example to `system/controlDict` or label the path as Foundation-only.
