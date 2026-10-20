# T-003: Correct the README examples, module aliases, CLI naming and release tags

- **Issue:** [#10](https://github.com/mcgoldba/foamkit/issues/10)
- **Type:** docs (owner: `docs-writer`)
- **Size:** S

## Goal
Every command and code snippet in `README.md` (also the PyPI landing page):
- uses the current names: the `fk` CLI, and the `fkf`/`fkt` module aliases;
- runs as written;
- is labelled when it needs OpenFOAM.

## Decisions (maintainer, 2026-10-18)
- **Module aliases** in docs and README: `import foamkit.functions as fkf` and `import foamkit.types as fkt`.
- **Release tags** use the `v` prefix (for example `v0.1.0`), which matches the CI trigger `refs/tags/v*`. `pyproject.toml` already has commitizen `tag_format = "v$version"`, so no config change is needed. Only the README is wrong.

## Known errors (from reading README.md)
- `import foamkit.functions as pf` / `import foamkit.types as pt` should become `fkf` / `fkt`. Update every `pf.`/`pt.` call in script examples.
- `case.constant.case.constant.turbulenceProperties...` is doubled, in two places.
- `import pamdas as pd` should be `pandas`.
- `samples = pd.DataFrame(...)` is later passed as `sample`.
- `turbulenceModels = [kEpsilon, ...]` and `= kOmega` use bare names. They need to be strings.
- `RAS.RASModel` / `turbulenceProperties` is only correct for ESI and older Foundation. Foundation 9+ pitzDaily uses `momentumTransport` / `RAS.model`. Label the example with the distribution it targets.
- `fkt.ofStudy(...)`: check the argument names and order against the `ofStudy` dataclass at `foamkit/types/__init__.py:3636-3643` (`templatePath, parameterNames, samples, updateFunction, path, runCommand`).
- The Scripting section uses `$FOAM_TEMPLATES`, which is probably meant to be `$FOAM_TUTORIALS`.
- Typos: "naitive", "dictonary", "manipultion", "parameteric", "varibale".
- Releasing: tag `v$RELEASE` instead of `$RELEASE` (`git tag -a v$RELEASE ...`), or point to `cz bump`, which already uses `v$version`.

## `pf`/`pt` aliases still in code. Document them only; do not rename them here
CLAUDE.md requires a deprecation path for code renames, so these are left as they are and listed as a follow-up:
- `foamkit/commandline/_iPython_env.py:4-5`: the `fk edit` console pre-imports `pf` and `pt`. README console snippets must use `pf`/`pt` until this changes, and the README should say so in one line.
- `foamkit/commandline/__init__.py:1, 11` (internal imports) and `:102-103` (the `edit` help text lists `pf`/`pt`).
- Docstring examples: `foamkit/functions/extractLogData.py:40-41` and `foamkit/functions/monitors.py:33`.
- Internal `import foamkit.types as pt` in `foamkit/functions/getMonitor.py:2`, `getProbe.py:2` and `monitor.py:7`. These are private and need no change.

## Scope
- `README.md` only.
- Optionally `tests/docs/test_readme.py`, which runs the Python snippets that do not need OpenFOAM against a copy of `tests/fixtures/pitzDaily`.

## Out of scope
- Renaming aliases in code or in the console, which needs a deprecation path and is a follow-up code ticket
- Restructuring the README or moving content into the Sphinx docs
- Badges, logos
- Any `foamkit/` change

## Acceptance criteria
- [ ] Every item in "Known errors" is fixed or explicitly reported back as needing the maintainer.
- [ ] Script snippets use `fkf`/`fkt`. Console (`fk edit`) snippets use the names the console actually provides, with a one-line note.
- [ ] Every Python snippet that does not need OpenFOAM is executed (doc-example test or recorded run), and it passes.
- [ ] Snippets that need OpenFOAM or an interactive console (`cp $FOAM_TUTORIALS/...`, `fk edit`, `case.run()`, `study.run()`) are labelled.
- [ ] Every name a snippet uses (functions, classes, arguments, attributes) exists in the code (checked with grep).
- [ ] The CLI is always `fk`; `pf` as a command appears at most once, as a deprecated-alias note.
- [ ] The Releasing section produces a `v`-prefixed tag.
- [ ] `git diff --stat -- foamkit/ pyproject.toml` is empty, and `pytest -q` passes.

## Risks
- The README is the PyPI long description. `twine check` in the `build` CI job must still pass.
- The `fkf` (scripts) vs `pf` (console) mismatch may confuse users until the follow-up code ticket lands. Keep the note short and explicit.
