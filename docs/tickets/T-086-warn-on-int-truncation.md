# T-086: assigning a fractional value to an integer entry (`d.deltaT.value = 0.001`) warns and stores the exact value instead of silently storing `0`

- **Issue:** [#114](https://github.com/mcgoldba/foamkit/issues/114)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (re-estimated for option B, 2026-11-09: the class change is one assignment in the `ofInt.value` setter, see Design; the rest is the scope already approved: the `ofInt`, `ofFloat` and `ofBool` setters plus one test in `DictFileParser._parseValue`)
- **Related:** T-020 (#27, T-020a fingerprint), T-071 (#101; `ofBoundBox`/`ofListGroups` groups hold `ofInt` items), T-080 (#107; counted-list lengths, not on `main` yet), T-081 (#108; dimension tokens read from files), T-087 (#115; `.value = None`, split out of this ticket's out-of-scope list), T-017 (`FoamKitError`), T-025 (`userMsg`).
- **Depends on:** none. It touches the scalar setters, not the writer, so it can land before or after T-020a.

## Maintainer decisions
- 2026-11-08: "lets ticket the truncation of float values, these should print a warning to the user."
- **2026-11-09: option B.** A fractional value assigned to an integer entry warns and **stores the exact value as a float**: the entry becomes an `ofFloat`, as `d.count = 4.5` already does. Stock pitzDaily `d.deltaT.value = 0.001` writes `deltaT 0.001;` plus one warning. (Option A, storing the truncated int, is dropped. CLAUDE.md's default, raising `FoamKitError`, was not chosen.)

## Goal
When a user assigns a value with a fractional part to an integer entry, FoamKit stores the exact value as a float and prints one warning naming the entry, the value given and that the entry is now a float. Values with no fractional part (`4.0`) stay integers, silently. A value that is not a number raises `FoamKitError` naming the entry instead of a bare `ValueError`, `OverflowError`, `TypeError` or `KeyError`.

## Today (planner, reproduced on 839663c = `origin/main`, 2026-11-08; unchanged on 2026-11-09)
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

All the truncating rows go through one line: `self._value = int(v)` in `ofInt.value`'s setter. File loading never reaches it: file tokens are strings, and `_fileInt('4.5')` raises before `int()` truncates anything.

## Design: how the entry becomes an `ofFloat` (planner, 2026-11-09)
**Chosen: an in-place class change in the `ofInt.value` setter** (`self.__class__ = ofFloat`, then `self._value = float(v)`), only when `type(self) is ofInt`.
- **Why this one:** the setter has no link to the dict, list or group that holds the entry, so it cannot replace the object. Changing the class of the same object updates every holder at once: a top-level entry, a sub-dict entry, an `ofList`/`ofSplitList` item, and an `ofListGroups`/`ofBoundBox` group item. No parent link is needed (that would touch every container and the cache).
- **Rejected: "store a float in an `ofInt`".** The entry would report `ofInt` (`isinstance`, `_type`, the cache) while holding a float, which is the confusing state the maintainer's choice avoids.
- **Checked on main (839663c, probe on pitzDaily `deltaT`):** `ofInt` and `ofFloat` are plain dataclasses with the same instance layout (no `__slots__`), so the assignment works. Afterwards `_type` is `'ofFloat'`, `attrDict()` gives `{'_name': 'deltaT', '_value': 0.001, '_type': 'ofFloat'}`, the dict writes `deltaT      0.001;`, and `copy.deepcopy` and `pickle` give an `ofFloat`. `ofInt` has no subclasses.
- **`isinstance` users:** `_numberReprs`, `_boxGroups`, `ofBoundBox.value` and `ofFoamFile` accept `(ofInt, ofFloat)` together, so they keep working. `_numberReprs` compares `repr(value)` (`'2'` vs `'2.5'`), so a changed group item drops its source text and is written as edited (T-071).
- **`.params` cache:** `_type` is computed from the class, so the cache saves `ofFloat` and `fk load` rebuilds an `ofFloat`. Test: `save` → `load` → `write` gives `deltaT 0.001;`.
- **T-020a fingerprint:** the fingerprint includes `_type`, so the change is always seen as an edit, even where the old and new numbers compare equal.
- **Constructor:** `ofInt(value=4.5)` and `ofInt('n', 4.5)` go through the same setter, so they return an object whose class is `ofFloat`, with the warning. That is intended: the user asked for 4.5.
- **Guard:** if `type(self) is not ofInt` (a future subclass), the setter raises `FoamKitError` for a fractional value instead of changing the class; the subclass decides.

## How the warning is shown
Through `userMsg(msg, 'WARNING')`, the path T-016 uses for unknown directives and `ofDict` uses for reserved names: one literal `WARNING:` line, no traceback. **`userMsg` only, no `warnings.warn` as well** (`warnings.warn` is used here only for `DeprecationWarning`; both would print twice in a console session).

Suggested text: `Integer entry 'deltaT': 0.001 is not a whole number; stored as a float (the entry is now an ofFloat).` An item with no name (list or group item) says `Integer list item: 2.5 is not a whole number; stored as a float.` Naming the containing entry would need a parent link, which is out of scope.

## Scope
- `foamkit/types/__init__.py`:
  - `ofInt.value` setter. A `numbers.Real` that is not a `bool`, or a string that `float()` accepts, is checked with `float(v).is_integer()` (exact, not `isclose`):
    - Integral values are stored silently as `int`.
    - Fractional values warn once per assignment, then change the class to `ofFloat` and store `float(v)` (see Design).
    - `None` keeps today's meaning here; T-087 changes it.
    - Anything else raises `FoamKitError("Integer entry '<name>': '<v>' is not a number.")` and keeps the old value. That covers non-numeric strings, `nan`, `inf`, lists and other types.
  - `bool` on `ofInt.value` and `ofFloat.value` raises `FoamKitError`. OpenFOAM has no integer `true`, and `d.count = True` already makes an `ofBool`. The message suggests `d.<name> = True`.
  - `ofFloat.value` setter: non-numeric values (including `bool`) raise `FoamKitError` naming the entry.
  - `ofBool.value` setter: a value that is not in `OF_BOOL_VALUES` and is not `True`/`False` raises `FoamKitError` naming the entry and the accepted words, instead of a bare `KeyError`.
  - `DictFileParser._parseValue`: replace `isclose(int(value), float(value))` with an exact integrality check. `d.count = 4.000000001` and `d.l = [1, 4.000000001]` then store an `ofFloat`, as `4.5` does today, with no warning (nothing is lost).
- Tests: a new `tests/test_int_truncation.py`, using `tests/fixtures/pitzDaily/system/controlDict` (`deltaT`) and inline dicts for the other rows; console output captured with `capsys`, as the existing `userMsg` tests do.

## Out of scope (noted, not fixed here)
- `.value = None` writes `count None;`: T-087 (#115).
- `d.nu.dimensions = [...]` is ignored on write, and `ofDimension` accepts `'a'`: T-088 (#116).
- `ofVector`/`ofSymmTensor`/`ofTensor` setters accept a list as soon as *one* item is numeric (`[1, 'a', 2]` is stored); `ofList.value = [1, 2.5, 'a']` stores raw Python items. A different code path; proposed follow-up (T-082 rewrites the tensor writers).
- `ofFloat.value = inf` is stored and written `inf`; whether OpenFOAM reads that was not checked.
- Counted-list lengths: T-080 must apply the same rule when it adds them.
- A Python `warnings` category for FoamKit data warnings.

## Acceptance criteria
- [ ] **Failing tests first:** one test per truncating row of the table (`.value` on a named entry, the constructor, a list item, an `ofListGroups` item, an `ofBoundBox` item, `numpy.float64`, `Decimal`, `Fraction`, the string `'4.5'`). Each asserts **exactly one** `WARNING:` line containing the entry name (or "list item") and the value given.
- [ ] Each of those rows stores the exact value: the object is an `ofFloat` (`type(x) is ofFloat`, `x._type == 'ofFloat'`) with `.value == float(v)`, and it is the same object its holder (dict, list, group) has.
- [ ] `d.deltaT.value = 0.001` on the real pitzDaily `controlDict` warns once and writes `deltaT 0.001;` (other lines unchanged); after `save` → `load` the entry is still an `ofFloat` 0.001.
- [ ] `d.g.groups[0].value[0].value = 2.5` writes `(2.5 2) (3 4)`; `d.box.groups[1].value[0].value = 2.5` writes `(0 0 0) (2.5 2 3)`, and the other group keeps its source text.
- [ ] `4.0`, `'4'`, `np.int64(4)` and every value already exact stay `ofInt` with **no** output.
- [ ] `d.count = 4.000000001` and `d.l = [1, 4.000000001]` store `ofFloat` with the exact value, with no output.
- [ ] Each of `'abc'`, `nan`, `inf`, `[1]`, `True` on `ofInt.value`, `'abc'` and `True` on `ofFloat.value`, and `2` and `'maybe'` on `ofBool.value` raises `FoamKitError` naming the entry; the old value and the class are kept. No bare `ValueError`/`OverflowError`/`TypeError`/`KeyError` escapes.
- [ ] Loading and writing every file in `tests/releases/` and `tests/fixtures/pitzDaily` prints no new warning and writes the same text as before (pin with the existing corpus loop).
- [ ] `init` → `save` → `load` of the pitzDaily case prints no warning.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): store a fractional value given to an integer entry as a float, with a warning (T-086)`. The commit body names the type change, the `FoamKitError` changes (bare `ValueError`/`KeyError` → `FoamKitError`) and the `bool` change.

## Risks
- **Behaviour change:**
  - An integer entry given a fractional value is no longer an `ofInt`: code that checks `isinstance(e, ofInt)` afterwards sees `ofFloat`. Put this in the commit body.
  - Code that caught `ValueError` or `KeyError` from these setters now gets `FoamKitError` (an `Exception` subclass, still a `SystemExit` for one release, T-017), which does not catch as `ValueError`.
  - `ofInt.value = True` stops storing `1`; `d.x = 4.000000001` changes type from `ofInt` to `ofFloat`.
- **Class change:** unusual in Python. It is safe here because the two classes share their layout and nothing caches the class (checked above); the tests pin `deepcopy`, `pickle` and the cache.
- **Noise:** a script that assigns fractional values in a loop prints one line per assignment. That is intended.
- **OpenFOAM versions:** none. Whether an entry is integer comes from FoamKit's reading of the source text, not from the OpenFOAM release. OpenFOAM reads `deltaT 0.001;` in every release.
