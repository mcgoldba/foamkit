# T-051: "Layout and formatting" docs page

- **Issue:** [#68](https://github.com/mcgoldba/foamkit/issues/68)
- **Type:** docs (owner: `docs-writer`)
- **Size:** S
- **Depends on:** T-001 (#8, docs site skeleton), T-020 (#27, layout preserved on write), T-050 (#67, `fk format` and `format_on_write`). Start only when all three are merged, so the page documents a stable API.

## Goal
A user can read one page that explains how FoamKit lays out the files it writes. By default, unedited entries keep their layout. The page also covers how to reformat a file or case with `fk format` or `fkf.formatCase`, and how to turn on `format_on_write`.

## Scope
- New page `docs/formatting.md` (MyST), linked from the docs index.
- It covers:
  - the default policy: the layout of unedited entries is preserved and edited entries are written in the canonical style;
  - the canonical style rules from T-050;
  - `fk format <file|case>`, with exit codes and the all-or-nothing behaviour;
  - `fkf.formatDictFile` and `fkf.formatCase`;
  - the `format_on_write` key: `fk setConfig format_on_write True`, the `.params/config.ini` lookup relative to the working directory, and `case.write(format=...)`;
  - what happens when a file cannot be formatted safely (`FoamKitError` with file and line, nothing written).
- Examples use `import foamkit.functions as fkf` and `import foamkit.types as fkt`.

## Out of scope
- API reference or autodoc pages (deferred until T-010).
- Changing any code.

## Acceptance criteria
- [ ] One doc-example test under `tests/docs/` runs the page's Python example on a temporary copy of a `tests/releases/` fixture. It checks that the file is reformatted and that a second format leaves it unchanged.
- [ ] The `fk format` example on the page is run by a CLI test, or matches an existing one in `tests/test_cli.py`.
- [ ] `sphinx-build -W --keep-going -b html docs docs/_build/html` passes.
- [ ] `pytest -q` passes.

## Risks
- If T-050's style changes at approval or review, the page must follow it. That is why this ticket waits for T-050 to merge.
