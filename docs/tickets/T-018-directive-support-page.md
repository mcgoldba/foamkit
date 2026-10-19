# T-018: "Directive support" docs page, checked against `OF_DIRECTIVES`

- **Type:** docs (owner: `docs-writer`; `tester` for the drift test)
- **Size:** S
- **Depends on:** T-001 (Sphinx site) and T-016 (`OF_DIRECTIVES` registry). It is a separate ticket because T-001 is ranked after T-016.

## Goal
A user can see which OpenFOAM `#` directives FoamKit interprets, which it preserves verbatim without interpreting, and which are unsupported, along with the distributions and releases that use each one. The page cannot drift from the code.

## Scope
- `docs/directives.md`, added to the `index` toctree. It contains:
  - a table with one row per `OF_DIRECTIVES` entry: directive, status (interpreted / preserved verbatim / unsupported), distributions and releases, and a note;
  - how unknown directives behave: kept verbatim, one WARNING, exposed as `ofVerbatimDirective`;
  - a short example of `fkt.iterDirectives(case, status="verbatim")` that runs on a fixture case without OpenFOAM.
- `tests/docs/test_directives_page.py`: every key in `foamkit.types.OF_DIRECTIVES` appears on the page with the same status, and the page lists no directive that is not in the registry.
- A short paragraph stating that this page is the **backlog record**: directives marked "preserved verbatim" are the candidates for interpretation if a need comes up, and adding one starts with a ticket that references this page.

## Out of scope
- Generating the page automatically (a later option if the registry grows; the drift test is enough for now)
- API reference for `ofVerbatimDirective` / `iterDirectives` (the later reference-docs ticket)

## Acceptance criteria
- [ ] The strict Sphinx build (`sphinx-build -W --keep-going -b html docs docs/_build/html`) exits 0 with the page in the toctree.
- [ ] The drift test passes, and it fails if a registry entry is added or its status changes without a page update. Show this once in the PR by temporarily editing a scratch copy.
- [ ] The example runs, using the `fkf`/`fkt` aliases.
- [ ] The distribution and release data on the page is taken only from the T-016 inventory table.
- [ ] `git diff --stat -- foamkit/` is empty, and `pytest -q` passes.

## Risks
- The page restates registry data. The drift test is the guard; if it becomes a maintenance burden, switch to generating the table from the registry in `conf.py`.
