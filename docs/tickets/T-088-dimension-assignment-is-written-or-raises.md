# T-088: assigning `.dimensions` (`d.nu.dimensions = [0 1 -1 0 0 0 0]`) is written back, and a bad dimension set raises, instead of being silently ignored or zeroed

- **Issue:** [#116](https://github.com/mcgoldba/foamkit/issues/116)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one validator used by the `ofDimension` setter, a `dimensions` property on `ofDimensionedScalar`, and two attribute guards on `ofNamedDimension`)
- **Related:** T-014 (#21; `nu nu [dims] value`, the bracket reader with spaces inside), T-081 (#108; which dimension sets are typed when read), T-013 (#20; named units and dimension sets such as `[velocity]`), T-086 (#114; same "integral or error" rule for numbers), T-020 (#27; edited entries are regenerated).
- **Depends on:** **T-014** (#21) and **T-081** (#108). T-014 changes `ofNamedDimension` and adds the bracket reader that this ticket reuses for string input; T-081 fixes the read-side rule (a typed dimension set is exactly 7 integers, everything else stays text) that this ticket applies to assignments. Order: T-014 → T-081 → T-088. T-013 lands later and widens the accepted strings to named sets.

## Goal
A user who assigns a dimension set to a dimensioned entry sees it written back; an assignment FoamKit cannot store as a valid OpenFOAM dimension set raises `FoamKitError` naming the entry and the expected shape, and stores nothing.

## Today (planner, reproduced on 839663c = `origin/main`, 2026-11-09)
Inputs: `nu [0 2 -1 0 0 0 0] 1e-05;` (top level and in a sub-dict) loads as `ofDimensionedScalar`, which keeps its set in `.dimension` (singular, an `ofDimension`). `dimensions [0 1 -1 0 0 0 0];` (field files) and `nu nu [0 2 -1 0 0 0 0] 1e-05;` load as `ofNamedDimension`, which keeps it in `.dimensions`. No row prints anything.

`ofDimensionedScalar` (`nu [0 2 -1 0 0 0 0] 1e-05;`, top level and sub-dict alike):

| Assignment | Stored | Written |
|---|---|---|
| `.dimensions = [0, 1, -1, 0, 0, 0, 0]`, `'[0 1 -1 0 0 0 0]'`, an `ofDimension`, `[0, 1, -1]`, `[0, 'a', -1, 0, 0, 0, 0]` | **a new, unused attribute** | **unchanged `nu [0 2 -1 0 0 0 0] 1e-05;`** |
| `.dimension = [0, 1, -1, 0, 0, 0, 0]` | the raw list | **`nu [0, 1, -1, 0, 0, 0, 0] 1e-05;`** (Python list text; OpenFOAM cannot read it) |
| `.dimension = [0, 1, -1]`, `[0, 'a', -1, 0, 0, 0, 0]`, `[0, 2.5, …]` | the raw list | **`[0, 1, -1]`**, **`[0, 'a', -1, …]`**, **`[0, 2.5, …]`** |
| `.dimension = '[0 1 -1 0 0 0 0]'` / an `ofDimension` | the string / object | `nu [0 1 -1 0 0 0 0] 1e-05;` (works; any string is written as given) |

`ofNamedDimension` (`dimensions [0 1 -1 0 0 0 0];`, `nu nu [...] 1e-05;`):

| Assignment | Stored | Written |
|---|---|---|
| `.dimensions = [0, 2, -1, 0, 0, 0, 0]` | the list | `dimensions [0 2 -1 0 0 0 0];` (correct) |
| `.dimensions = '[0 1 -1 0 0 0 0]'`, an `ofDimension`, a tuple `(0, 1, -1, 0, 0, 0, 0)`, `None` | **`[0, 0, 0, 0, 0, 0, 0]`** | **`dimensions [0 0 0 0 0 0 0];`** (the set is silently zeroed) |
| `.dimensions = [0, 'a', -1, 0, 0, 0, 0]`, `[0, 2.5, -1, …]` | the list | **`[0 a -1 0 0 0 0]`**, `[0 2.5 -1 0 0 0 0]` (accepted because *one* item is an `int`) |
| `.dimensions = [0, 1, -1]` | unchanged | bare `ValueError` with a 7-line help text, no entry name |
| `.value = [...]`, `.dimension = [...]` | **a new, unused attribute** | **unchanged** |

`fkt.ofDimension(v)` and `ofDimension.dimensions = v`: `'a'`, `'[0 1 -1 0 0 0 0]'`, `(0, 1, -1, 0, 0, 0, 0)` and `None` all give **`[0 0 0 0 0 0 0]`**; `[0, 'a', 0, 0, 0, 0, 0]` gives **`[0 a 0 0 0 0 0]`**; `[0, 1]` raises the bare `ValueError`.

Cause: `ofDimension.dimensions`'s setter replaces any non-list with zeros and checks `any(isinstance(i, int) …)` instead of `all`; `ofDimensionedScalar` has no `dimensions` attribute (it writes `str(self.dimension)`), and neither class guards the other's attribute name.

Real files: 0 (users trigger it). Changing a dimension set by hand is rarer than changing a value, but the zeroed and ignored rows are silent, and `.dimensions` is the name the field-file entry and `ofDimension` already use.

## Design (planner, 2026-11-09)
- **One validator** (for example `_dimensionSet(v, entry)`), used by every assignment and by `ofDimension(...)`. It accepts:
  - a list or tuple of exactly 7 numbers, each an integer or an integral real (`2.0` → `2`, as T-086 does for integers); `bool` is refused;
  - a string `[e1 … e7]` with 7 integer exponents, read with T-014's bracket reader (any spacing inside the brackets);
  - an `ofDimension` (its list is copied).
  It stores a plain list of 7 `int`s. Anything else raises `FoamKitError("Entry 'nu': dimensions must be 7 integer exponents, e.g. [0 2 -1 0 0 0 0]; got '<v>'.")` and keeps the old set: wrong length (including the 5-exponent form), fractional exponents, words, named sets such as `'[velocity]'` (until T-013), `None` on an existing entry. This matches what T-081 types on read; sets FoamKit keeps as text on read (5 exponents, fractional) are assigned as text, not through `.dimensions`.
- **`.dimensions` is the public name on every dimensioned type.** `ofDimensionedScalar` gains a `dimensions` property: it reads `self.dimension.dimensions` and sets through the validator. Assigning `.dimension` (the existing `ofDimension` attribute, used by the `.params` cache) goes through the same validator and stores an `ofDimension`, so a list is never written as Python text. No rename, no deprecation.
- **`ofNamedDimension`** (a dimension set with no value, e.g. `dimensions [0 1 -1 0 0 0 0];`): assigning `.value` or `.dimension` raises `FoamKitError` that names the entry and points to `.dimensions`. If T-014 gives `nu nu [dims] value` a value attribute, that one is the exception.
- **Construction:** `ofDimension()` / `ofDimension(None)` keep today's default (all zeros); only explicit values go through the validator.
- **Write:** the stored set is written `[0 1 -1 0 0 0 0]`. The changed `dimension`/`_dimensions` attribute changes the entry's T-020a fingerprint, so the entry is regenerated; untouched entries stay as read.

## Scope
- `foamkit/types/__init__.py`: `ofDimension` (setter, constructor), `ofDimensionedScalar` (`dimensions` property, `dimension` assignment), `ofNamedDimension` (the two guards), and the dimensioned vector/tensor classes that inherit `ofDimension` (pin that they use the same setter).
- Tests: a new `tests/test_dimension_assignment.py`: every bold row, at the top level, in a sub-dict and in a field file (`tests/fixtures/pitzDaily/0/U` `dimensions`, `constant/transportProperties` `nu`).

## Out of scope
- Which dimension sets are typed when read (T-081), `nu nu [dims] value` (T-014), named units and named sets (T-013).
- Unit conversion or checking that a set fits the quantity.
- `.dimensions = None` meaning "remove the set" (T-087 covers `.value = None` only).

## Acceptance criteria
- [ ] **Failing tests first:** every bold row of the three tables.
- [ ] `d.nu.dimensions = v` for `v` = `[0, 1, -1, 0, 0, 0, 0]`, `(0, 1, -1, 0, 0, 0, 0)`, `'[0 1 -1 0 0 0 0]'`, `'[ 0 1 -1 0 0 0 0 ]'`, `[0, 1.0, -1, 0, 0, 0, 0]` and `ofDimension([0, 1, -1, 0, 0, 0, 0])` reads back `[0, 1, -1, 0, 0, 0, 0]` and writes `nu [0 1 -1 0 0 0 0] 1e-05;`, at the top level and in a sub-dict; the same for `.dimension`.
- [ ] The same inputs on `dimensions [0 1 -1 0 0 0 0];` (pitzDaily `0/U`) write `dimensions [0 1 -1 0 0 0 0];`; none gives zeros.
- [ ] `[0, 1, -1]`, `[0, 'a', -1, 0, 0, 0, 0]`, `[0, 2.5, -1, 0, 0, 0, 0]`, `[0, True, 0, 0, 0, 0, 0]`, `'a'`, `'[velocity]'`, `'[0 2 -1 0 0]'` and `None` raise `FoamKitError` naming the entry and the expected shape, on `ofDimensionedScalar`, `ofNamedDimension` and `ofDimension(...)`; the old set is kept and the written file is unchanged. No bare `ValueError` escapes.
- [ ] `.value =` and `.dimension =` on an `ofNamedDimension` raise `FoamKitError` pointing to `.dimensions`.
- [ ] `case.save()` → `fk load` → write keeps an assigned set (pitzDaily `nu`).
- [ ] Loading and writing every file in `tests/releases/` and `tests/fixtures/pitzDaily` writes the same text as before.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write assigned dimension sets and reject invalid ones (T-088)`; the commit body names the new `FoamKitError`s and that `ofDimension('...')` no longer gives zeros.

## Risks
- **Behaviour change:** code that relied on `ofDimension('anything')` giving zeros, or on the bare `ValueError`, now gets a parsed set or `FoamKitError`.
- **Old `.params` caches:** a cache saved after `d.nu.dimensions = [...]` holds the stray `dimensions` key. On load it now goes through the property, so the set the user assigned is applied (what they asked for); an invalid stray value raises `FoamKitError` naming the entry on load. Test one such cache.
- **OpenFOAM versions:** OpenFOAM also accepts 5-exponent and fractional sets; refusing them on assignment is FoamKit's choice for typed sets (T-081 keeps them as text when read).
