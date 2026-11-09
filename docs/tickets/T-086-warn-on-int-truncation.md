# T-086: assigning a fractional value to an integer entry (`d.deltaT.value = 0.001`) warns instead of silently storing `0`

- **Issue:** [#114](https://github.com/mcgoldba/foamkit/issues/114)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (the three scalar `.value` setters, `ofInt`, `ofFloat` and `ofBool`, plus one test in `DictFileParser._parseValue`)
- **Related:** T-020 (#27, T-020a fingerprint), T-071 (#101; `ofBoundBox`/`ofListGroups` groups hold `ofInt` items), T-080 (#107; counted-list lengths, not on `main` yet), T-081 (#108; dimension tokens read from files), T-017 (`FoamKitError`), T-025 (`userMsg`).
- **Depends on:** none. It touches the scalar setters, not the writer, so it can land before or after T-020a.

## Maintainer decision (2026-11-08)
> "lets ticket the truncation of float values, these should print a warning to the user."

**Decision to confirm at approval:** what is stored after the warning.
- **Option A (default, as the maintainer said):** warn, then store the truncated int, as today. `d.deltaT.value = 0.001` warns and still writes `deltaT 0;`.
- **Option B:** warn, then store the exact float by turning the entry into an `ofFloat`, which is what `d.deltaT = 0.001` already does. The setter has no link to the dict that holds the entry, so B means swapping the object's class in place (`self.__class__ = ofFloat`) or adding a parent link. That may make B a size M.
- Not offered, but noted: CLAUDE.md's default would be to raise `FoamKitError`. The maintainer chose a warning.

## Goal
When a user assigns a value with a fractional part to an integer entry, FoamKit prints one warning naming the entry, the value given and the value stored. Values with no fractional part (`4.0`) stay silent. A value that is not a number raises `FoamKitError` naming the entry instead of a bare `ValueError`, `OverflowError`, `TypeError` or `KeyError`.

## Today (planner, reproduced on 839663c = `origin/main`, 2026-11-08)
Real stock pitzDaily `system/controlDict` (`tests/fixtures/pitzDaily`): `deltaT 1;` loads as `ofInt`. After `d.deltaT.value = 0.001` it is `ofInt 0`, written **`deltaT      0;`**, with no message.

Probe dict with `count 4;`, `x 1.5;`, `flag on;`, `l (1 2 3);`, `g (1 2) (3 4);`, `box (0 0 0) (1 2 3);`:

| Assignment | Result today |
|---|---|
| `d.count = 4.0` / `4.5` / `'abc'` | `ofInt 4` / `ofFloat 4.5` / `ofStr abc` (correct) |
| `d.count = 4.000000001` | **`ofInt 4`, written `4`**: `_parseValue` uses `isclose(int(v), float(v))` (relative tolerance 1e-9) |
| `d.l = [1, 4.000000001]` | **second item `ofInt 4`** (same `_parseValue` path) |
| `d.count.value = 4.0` / `'4'` | `ofInt 4` (correct) |
| `d.count.value = 4.5`, `4.000000001`, `np.float64(4.5)`, `Decimal('4.5')`, `Fraction(9, 2)` | **`ofInt 4`, written `4`, silently** |
| `ofInt(value=4.5)`, `ofInt('n', 4.5)` | **`.value == 4`, silently** (the constructor uses the setter) |
| `d.l.value[0].value = 2.5` | **list item `ofInt 2`, silently** |
| `d.g.groups[0].value[0].value = 2.5` (`ofListGroups`) | **written `(2 2) (3 4)`, silently** |
| `d.box.groups[1].value[0].value = 2.5` (`ofBoundBox`) | **written `(0 0 0) (2 2 3)`, silently** |
| `d.count.value = True` | **`ofInt 1`, written `1`** |
| `d.count.value = 'abc'`, `'4.5'`, `nan` | bare `ValueError: ofInt value must be an integer.` |
| `d.count.value = inf` / `[1]` | bare `OverflowError` / bare `TypeError` |
| `d.x.value = 'abc'`, `'1.5x'` (`ofFloat`) | bare `ValueError: ofFloat value must be a numeric.` |
| `d.x.value = True` | **`ofFloat 1.0`, written `1.0`** |
| `d.flag.value = 2`, `0`, `1.0`, `'maybe'` (`ofBool`) | bare `KeyError` |

All the truncating rows go through one line: `self._value = int(v)` in `ofInt.value`'s setter. Other places that call `int()` on a user value: `_boxGroups` (only on `numbers.Integral`, so it never truncates). Dimension exponents are stored as given, not passed through `int()`: `[0 2.5 …]` is kept as `2.5`. On `main` no counted-list length comes from a user value (counted lists are T-080). File loading never reaches the truncation: file tokens are strings, and `_fileInt('4.5')` raises before `int()` truncates anything.

## How the warning is shown
Through `userMsg(msg, 'WARNING')`, the path T-016 uses for unknown directives and `ofDict` uses for reserved names. It prints one literal `WARNING:` line to the rich console (to the logger at DEBUG level), with no traceback. **Recommended: `userMsg` only, no `warnings.warn` as well.** `warnings.warn` is used in this codebase only for `DeprecationWarning` (T-071). Calling both would print twice in a console session. Letting library users filter or escalate FoamKit's data warnings is a project-wide choice that would cover T-016's warning too, so it belongs in its own ticket if wanted.

Suggested text (option A): `Integer entry 'deltaT': 0.001 was stored as 0 (fractional part dropped). Assign d.deltaT = 0.001 to store a float.` An `ofInt` with no name (a list or group item has no link to its list) says `Integer list item: 2.5 was stored as 2 …`. Naming the containing entry would need a parent link, which is out of scope.

## Scope
- `foamkit/types/__init__.py`:
  - `ofInt.value` setter. A `numbers.Real` that is not a `bool`, or a string that `float()` accepts, is checked with `float(v).is_integer()` (exact, not `isclose`):
    - Integral values are stored silently as `int`.
    - Fractional values warn once per assignment, then follow option A (or B).
    - `None` keeps today's meaning.
    - Anything else raises `FoamKitError("Integer entry '<name>': '<v>' is not a number.")`. That covers non-numeric strings, `nan`, `inf`, lists and other types.
  - `bool` on `ofInt.value` and `ofFloat.value` raises `FoamKitError`. OpenFOAM has no integer `true`, so storing `1` silently changes the meaning, and `d.count = True` already makes an `ofBool`. The message suggests `d.<name> = True`.
  - `ofFloat.value` setter: non-numeric values (including `bool`) raise `FoamKitError` naming the entry. This is the same pattern in the next setter, so it is included.
  - `ofBool.value` setter: a value that is not in `OF_BOOL_VALUES` and is not `True`/`False` raises `FoamKitError` naming the entry and the accepted words, instead of a bare `KeyError`. This is a different lookup but the same bare-exception class of bug, a few lines long, so it is included.
  - `DictFileParser._parseValue`: replace `isclose(int(value), float(value))` with an exact integrality check. `d.count = 4.000000001` and `d.l = [1, 4.000000001]` then store an `ofFloat`, as `4.5` does today. No warning is needed here because nothing is lost.
- Tests: a new `tests/test_int_truncation.py`, using `tests/fixtures/pitzDaily/system/controlDict` (`deltaT`) and inline dicts for the other rows. It captures the console output (`capsys`), as the existing `userMsg` tests do.

## Out of scope (noted, not fixed here)
- `ofInt.value = None` / `ofFloat.value = None` write `count None;`, which neither FoamKit nor OpenFOAM can read. This is a separate silent-invalid-write bug, and the `None` branch is also what constructors use when no value is given. It needs its own ticket.
- `ofVector`/`ofSymmTensor`/`ofTensor` setters accept a list as soon as *one* item is numeric (`any(...)`), so `[1, 'a', 2]` is stored. `ofList.value = [1, 2.5, 'a']` stores raw Python items. Both are a different code path; proposed follow-up ticket (T-082 rewrites the tensor writers).
- `ofDimension.dimensions` accepts `'a'` (written `[0 2.5 a 0 0 0 0]`), and `d.nu.dimensions = [...]` on an `ofDimensionedScalar` sets an unused attribute, so the write is unchanged with no error. Dimension handling belongs to T-081 and T-014 (to add to them when they are next refreshed).
- `ofFloat.value = inf` is stored and written `inf`; whether OpenFOAM reads that was not checked.
- Counted-list lengths: T-080 must apply the same rule when it adds them (to add to T-080 when the planner next refreshes it).
- A Python `warnings` category for FoamKit data warnings (see above).

## Acceptance criteria
- [ ] **Failing tests first:** one test per truncating row of the table (`.value` on a named entry, the constructor, a list item, an `ofListGroups` item, an `ofBoundBox` item, `numpy.float64`, `Decimal`, `Fraction`, the string `'4.5'`). Each asserts **exactly one** `WARNING:` line containing the entry name (or "list item"), the value given and the value stored.
- [ ] Stored values: option A (or B if chosen) for fractional values. `4.0`, `'4'`, `np.int64(4)` and every value already exact are stored as today with **no** output.
- [ ] `d.deltaT.value = 0.001` on the real pitzDaily `controlDict` warns once. Under A it writes `deltaT 0;`; under B it writes `deltaT 0.001;`.
- [ ] `d.count = 4.000000001` and `d.l = [1, 4.000000001]` store `ofFloat` with the exact value, with no output.
- [ ] Each of `'abc'`, `nan`, `inf`, `[1]`, `True` on `ofInt.value`, `'abc'` and `True` on `ofFloat.value`, and `2` and `'maybe'` on `ofBool.value` raises `FoamKitError` naming the entry, with the old value kept. No bare `ValueError`/`OverflowError`/`TypeError`/`KeyError` escapes.
- [ ] Loading and writing every file in `tests/releases/` and `tests/fixtures/pitzDaily` prints no new warning and writes the same text as before (pin with the existing corpus loop).
- [ ] `init` → `save` → `load` of the pitzDaily case prints no warning.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): warn when a fractional value is stored in an integer entry (T-086)`. The commit body names the `FoamKitError` changes (bare `ValueError`/`KeyError` → `FoamKitError`) and the `bool` change.

## Risks
- **Behaviour change:**
  - Code that caught `ValueError` or `KeyError` from these setters now gets `FoamKitError`. That class is an `Exception` subclass (and still a `SystemExit` for one release, T-017), so it does not catch as `ValueError`. Put this in the commit body.
  - `ofInt.value = True` stops storing `1`.
  - `d.x = 4.000000001` changes type from `ofInt` to `ofFloat`.
- **Option A keeps the loss:** the warning is the only sign that `deltaT 0;` will be written. Under A, `d.count.value = 4.5` on `count 4;` stores `4` again, so a value fingerprint (T-020a) sees no change and the entry is written from source, which is correct for what is stored. When the stored int differs (`7.5` on `count 4;` → `7`), the edit is detected because the value changes. Under B the type changes, so it is always detected.
- **Option B's mechanism:** an in-place class swap is unusual. The implementer should check `isinstance` users, `copy`/`pickle` (the `copyreg` cache) and `ofListGroups._numberReprs` before choosing it.
- **Noise:** a script that assigns fractional values in a loop prints one line per assignment. That is intended ("exactly once" per assignment, not once per session).
- **OpenFOAM versions:** none. Whether an entry is integer comes from FoamKit's reading of the source text, not from the OpenFOAM release.
