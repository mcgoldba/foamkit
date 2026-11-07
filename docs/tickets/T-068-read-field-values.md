# T-068: Read field values from a time directory as NumPy arrays

- **Issue:** [#88](https://github.com/mcgoldba/foamkit/issues/88)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** M (if binary or compressed fields turn out to be needed, they are a separate ticket; here they raise)
- **Track:** runtime (run, monitor, results)
- **Depends on:** T-063 (`timeDirs`)
- **Blocked by:** real written field files (see "Questions for the maintainer" in `ROADMAP.md`), unless the tester finds stock tutorials that ship `nonuniform` fields

## Goal
A user reads the internal and boundary values of a result field (`p`, `U`, …) at a given time as NumPy arrays, with the field class and dimensions, without OpenFOAM.

## Today (planner, 2026-11-06, a 4-value `nonuniform List<scalar>` and a 2-value `nonuniform List<vector>` field read with `fkf.readDictFile`)
- `internalField nonuniform List<scalar> 4 ( … );` loads as an `ofMultilineStatement` of tokens (`'nonuniform List<scalar>'`, `4`, `'('`, `1.5`, …), not as numbers; the same for vectors. There is no API that returns the values.
- `CaseParser` loads every time directory into the case object as `t_<time>` folders (`foamkit/types/__init__.py:1029-1050`), parsing each field file as a dictionary; `dict_filesize_limit` is only applied by `cloneCase` (`foamkit/functions/cloneCase.py:60`).

## Public names (approved with this ticket)
- `fkf.readField(path, field, time="latestTime") -> fkt.ofFieldValues` with `internal` (`numpy.ndarray`, shape `(n,)` for scalars, `(n, 3)` vectors, `(n, 6)` symmTensor, `(n, 9)` tensor), `boundary` (dict of patch name to an array, or to the uniform value), `fieldClass`, `dimensions`, `time`.
- Uniform values are returned as arrays of length 1 with `uniform=True` noted per entry, not expanded (the mesh size is not read).

## Scope
- A reader in `foamkit/functions/` (and the value class in `foamkit/types/`) that reads the `FoamFile` header and the `internalField`/`boundaryField` entries directly, line by line, without building the whole field as dictionary objects.
- `format binary;` and `.gz` files raise `FoamKitError` naming the file ("binary/compressed fields are not supported yet").
- A count that does not match the number of values, or a value of the wrong width, raises `FoamKitError` with file and line.
- Decomposed cases: `processor=<n>` reads one processor directory; reading a reconstructed time that does not exist raises and names `fkf.timeDirs`' list.

## Out of scope
- Mesh reading (points, cells), interpolation, and writing fields
- Changing what `CaseParser` loads into the case object (a separate ticket if loading large result fields is too slow)

## Acceptance criteria
- [ ] Fixtures: real field files (written by a run or shipped by a stock tutorial), trimmed, from at least Foundation 14 and ESI v2606, including scalar and vector `nonuniform` internal fields and a patch with `nonuniform` values; source recorded.
- [ ] Failing tests first: shapes and spot values match the file; uniform internal and patch values are returned as described.
- [ ] Binary, compressed, mismatched-count and wrong-width inputs each raise `FoamKitError` with the file (and line where there is one).
- [ ] Reading a 1,000,000-value scalar field built in `tmp_path` takes under 5 s on CI and does not go through `DictFileParser`.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline. A `feat:` commit.

## Risks
- Field files can hold `#include` or `$` references in `boundaryField` (for example `#include "include/initialConditions"`); such entries raise `FoamKitError` here rather than being resolved silently.
- Precision: values are read as `float64`; the original text is not kept (read-only API).
