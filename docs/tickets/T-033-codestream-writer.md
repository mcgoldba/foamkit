# T-033: `#codeStream` writer is unstable (adds blank lines on every write)

- **Issue:** [#44](https://github.com/mcgoldba/foamkit/issues/44)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S

## Goal
A `#codeStream` entry is written back unchanged, and repeated writes are stable.

## Evidence (real tutorial trees, 2026-10-21; from the T-016 tester)
- `#codeStream`: Foundation 1/1/1/4 files in 11/12/13/14, ESI 14. It loads, but the writer:
  - writes `vertices #codeStream{` (the `{` is moved onto the directive line);
  - **adds a blank line per source line on each write**, so the file grows every time it is written. The existing `test_repeated_writes_converge` guard does not cover a real `#codeStream` file.
- Real examples:
  - Foundation 14 `floatingBeam/system/blockMeshDict:21` `vertices #codeStream` (`tests/releases/foundation-14.floatingBeam.blockMeshDict`; it also needs T-030 for line 17);
  - ESI v2606 `basic/potentialFoam/cylinder/system/blockMeshDict:41` (`tests/releases/esi-v2606.potentialFoam-cylinder.blockMeshDict`; it also needs T-031 and T-016).

## Scope
- `ofCodeStream` / verbatim-code `toString` and re-indentation in `foamkit/types/__init__.py`. Keep the brace placement and the code text byte-for-byte for unedited entries.

## Out of scope
- Running or validating the code
- `#{ #}` blocks in other entries, unless they show the same bug (then include them, and record it)

## Acceptance criteria
- [ ] **Failing tests first** on a snippet copied from a real `#codeStream` entry (record its source):
  - write 1 differs from the source in brace placement and blank lines;
  - write 2 differs from write 1.
- [ ] After the fix, the snippet round-trips byte-identically, and write 1 == write 2 == write 3. This holds at top level and in value position (`vertices #codeStream`).
- [ ] Existing `#codeStream`/`#{ #}` tests and goldens (`tests/golden/dicts/dicts/functionEntries.txt`) are unchanged, or any diff is limited to now matching the source and is reviewed.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **The verbatim-code indentation logic is shared with `codeExecute`-style entries.** The existing goldens guard them.

## Ranking rationale
Medium: the case loads, but each write corrupts the file a little more. It is S.
