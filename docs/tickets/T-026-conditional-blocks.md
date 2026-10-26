# T-026: Conditional blocks `#if` / `#ifeq` / `#else` / `#endif` kept verbatim

- **Issue:** [#37](https://github.com/mcgoldba/foamkit/issues/37)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M
- **Depends on:** T-016 (`ofVerbatimDirective`, `OF_DIRECTIVES`)
- **Split from:** T-016, 2026-10-21 (maintainer-approved)

## Goal
Files that use conditional blocks load, and are written back with the whole block unchanged. This includes Foundation 13/14 `fvSchemes` and the ESI dictionaries.

## Evidence (real tutorial trees, 2026-10-21; see the plan's Directive inventory)
- `#ifeq`, `#else`, `#endif`: Foundation 13 and 14, and ESI. Example: Foundation 14 `incompressibleFluid/cylinder/system/fvSchemes:39` (`tests/releases/foundation-14.cylinder.fvSchemes`):
  ```
  #ifeq ($!ddtSchemes/default steadyState)
      div(phi,U)      bounded Gauss linearUpwind limited;
      ...
  #else
      ...
  #endif
  ```
- `#if`: ESI only, 16 files.
- **Nesting:** ESI `IO/dictionary/good-if1.dict:17-28` has an `#if #calc "...";` block inside an `#ifeq` block (`tests/releases/esi-v2606.good-if1.dict`).
- **Dead branches with unbalanced braces:** ESI `good-if3.dict` (`tests/releases/esi-v2606.good-if3.dict`). So the capture must be **textual**, line by line, to the matching `#endif`. It must not parse the branches.
- All of these fail today with "Could not find functionEntry bracket type".

## Scope
- In `DictFileParser`, when a line starts with `#if`, `#ifeq`, `#ifneq` or `#ifdef`, capture the raw text from that line to the **matching** `#endif`. Count nested `#if*`/`#endif` pairs, and ignore braces and quotes inside the block. Store it as one `ofVerbatimDirective(keyword="ifeq", text=...)` (T-016 type) at that position, at top level or inside a sub-dict. Check the exact keyword list against the ESI/Foundation dictionary sources and record it.
- Update the `OF_DIRECTIVES` rows for `if`, `ifeq`, `else` and `endif` from `"unsupported"` to `"verbatim"`.
- Document in the docstrings that entries inside a conditional block are not editable through attributes.

## Out of scope
- Evaluating conditions or choosing a branch
- `#calc` inside the condition (it stays part of the verbatim text)

## Acceptance criteria
- [ ] **Failing tests first** with the real fixtures `foundation-14.cylinder.fvSchemes`, `esi-v2606.good-if1.dict` and `esi-v2606.good-if3.dict`.
- [ ] After the fix, all three load, and each conditional block is written back byte-identical to its source lines.
- [ ] Nested blocks produce **one** verbatim directive for the outermost block.
- [ ] Unbalanced braces or quotes inside a dead branch do not affect the capture.
- [ ] Entries before and after the block parse normally and stay editable.
- [ ] An unterminated block (no matching `#endif`) raises `FoamKitError` with the file and the line of the opening `#if*`. A stray `#else` or `#endif` with no opening `#if*` also raises `FoamKitError` with the file and line.
- [ ] `iterDirectives(..., status="verbatim")` lists the blocks.
- [ ] All existing golden files are unchanged. `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Large captured blocks:** the scan must be linear, and bounded by the end of the file with an error.
- **Users may expect to edit inside a conditional.** Document that they cannot; the T-018 page lists it.

## Ranking rationale
Ranked third, after T-016 and T-027. It blocks real Foundation 13/14 `fvSchemes` and ESI files, but it is less widespread than value-position `#calc`/`#neg` (T-027, more than 100 files per Foundation release).
