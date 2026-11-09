# T-087: `d.count.value = None` writes the keyword-only entry `count;` with a warning, instead of `count None;`

- **Issue:** [#115](https://github.com/mcgoldba/foamkit/issues/115)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one helper called from the `.value` setters, one check in each of the two dict writers, one branch in `ofDict.__setattr__`)
- **Related:** T-079 (#106; top-level keyword-only entries load), T-086 (#114; the same setters; this ticket was its out-of-scope `None` row), T-020 (#27; the writer for edited entries), T-076 (#103; `groups.clear()` on a box), T-071 (#101; `ofBoundBox`).
- **Depends on:** **T-079** (#106). Without it the written top-level `count;` cannot be read back by FoamKit (bare `AttributeError`), so write 2 is impossible. Order: T-079, then this ticket. Also start after T-020a and T-086 merge (same file, same setters).

## Maintainer decision (2026-11-09)
> "`.value = None` should write `count;`, and raise a warning."

## Goal
Assigning `None` to the value of a named entry writes the keyword-only entry `count;` (valid OpenFOAM) and prints one warning naming the entry, instead of silently writing `count None;`, which OpenFOAM cannot read as a number and reads as the word `None` elsewhere.

## Today (planner, reproduced on 839663c = `origin/main`, 2026-11-09)
Probe dict with `count 4;`, `x 1.5;`, `s abc;`, `w "q";`, `flag on;`, `l (1 2 3);`, `g (1 2) (3 4);`, `box (0 0 0) (1 2 3);`, `nu [0 2 -1 0 0 0 0] 1e-05;`, `u uniform (0 0 0);`, `r $a;`. No row prints anything.

| Assignment | Stored | Written |
|---|---|---|
| `d.count.value = None` (`ofInt`) | `ofInt`, `.value None` | **`count       None;`** |
| `d.x.value = None` (`ofFloat`), `d.s`/`d.w` (`ofStr`) | `.value None` | **`x           None;`**, **`s           None;`** |
| `d.flag.value = None` (`ofBool`) | `.value None` | `flag        ;` (padded; top-level re-read: bare `AttributeError`, T-079; in a sub-dict write 2 is `flag;`, so write 1 != write 2) |
| `d.l.value = None` (`ofSplitList`) | **`.value == []`** | **`l ( );`** over three lines: an empty list, not what was asked |
| `d.g.value = None` (`ofListGroups`) | `.value == []` | `g           ;` (padded) |
| `d.box.value = None` (`ofBoundBox`) | unchanged | `FoamKitError` "expected 2 groups of 3 real numbers" (loud, T-071) |
| `d.nu.value = None` (`ofDimensionedScalar`) | `.value None` | **`nu          [0 2 -1 0 0 0 0] None;`** |
| `d.u.value = None` (`ofUniformField`) | `.value None` | **`u           uniform None;`** |
| `d.r.value = None` (`ofVar`) | `.value 'None'` | **`r           $None;`** |
| `ofVector('k', [1, 0, 0]).value = None` | **`[0.0, 0.0, 0.0]`** | **`k           (0.0 0.0 0.0);`** |
| `d.count = None` | **Python `None`** replaces the `ofInt` | **`count       None`** (no `;`) |
| `d.sub.count = None` (sub-dict) | Python `None` | **`    count   None;`** |
| `d.new = None` (new key) | Python `None` | **`new         None`** (no `;`) |
| `d.sub.value = None` (`ofDict`) | a new key `value` | **`    value   None;`** |
| `d.l.value[0].value = None` (list item) | item `.value None` | **`None`** as a list item |

Re-read of the written text: `count None;` in a sub-dict loads as **`ofStr 'None'`** (the type changes silently); at the top level likewise.

Keyword-only entries read from files (for comparison): in a multi-line sub-dict, `count;` and `count     ;` load as `ofWord('count')` under the key `unnamed_<n>` and are written `count;` (indented, no padding: the `ofWord.toString` comment explains why). At the top level they crash with a bare `AttributeError` until T-079 (option A: the same `unnamed_<n>` `ofWord`). In a one-line `{ … }` block they raise `FoamKitError` (T-040).

## Design (planner, 2026-11-09)
- **Type afterwards:** the entry keeps its class and its key (`d.count` is still the same `ofInt` object). **`.value` reads `None`.** A later `d.count.value = 5` gives back `count 5;`.
- **Written:** `count;`, at the dict's indent, with no value column padding, exactly as file keyword-only entries are written today. Any `// comment` the entry carries is kept after the `;`. The dimension set of a dimensioned entry and the `uniform` of a field are not written (the user removed the value).
- **Warning:** `userMsg("Entry 'count': value set to None; written as the keyword-only entry 'count;'.", 'WARNING')`, once per assignment, **only when the old value was not `None`**. That keeps constructors (`ofInt(name='n')` sets `None` before any value exists) and the `.params` cache load (which sets `_value` directly) silent. A new key that never had a value does not warn because it raises (below).
- **Which setters:** every named value type: `ofInt`, `ofFloat`, `ofStr`, `ofBool`, `ofVar`, `ofList`/`ofSplitList`, `ofListGroups`, `ofBoundBox`, `ofVector` and its tensor subclasses, `ofDimensionedScalar` and the dimensioned vector/tensor types, `ofUniformField`. One helper (for example `_setKeywordOnly(self)`) does the check, the warning and `self._value = None`. Construction keeps today's defaults (`ofList()` is `[]`, `ofVector()` is `[0.0, 0.0, 0.0]`): the rule applies only when the object already has a `_value`.
  - `ofBoundBox`: `None` becomes keyword-only too (the maintainer's rule covers every typed entry); other bad values keep T-071's `FoamKitError`. `groups.clear()` stays T-076's case.
- **Writers:** one check in each of the two dict writers (the sub-dict `ofDict.toString` and the top-level file writer, including T-020a's path for edited entries): a named value entry whose `_value is None` is written `name;`. The per-class `toString` methods do not change. An entry built with no value (`d.update(fkt.ofInt(name='n'))`, today written `n None;`) is then also written `n;`, without a warning (nothing was replaced).
- **`d.count = None`** (`ofDict.__setattr__`): if `count` holds a named value entry, this is the same as `d.count.value = None` (same object kept, same warning). If the key is new, or holds a sub-dict, a directive or other non-value entry, it raises `FoamKitError("Cannot set 'count' to None: …")` that suggests `del d.count` to remove an entry and `d.count = fkt.ofWord('count')` to add a keyword-only one (that already writes `count;` on main). This keeps one in-memory form per case and never replaces a whole sub-dict silently. `d.sub.value = None` on a dict with no `value` entry is the new-key case and raises; on a boundary patch with `value uniform 0;` it is the value-entry case.
- **Unnamed items** (a list or group item, `d.l.value[0].value = None`): an item cannot be keyword-only, so this raises `FoamKitError` naming the list item and suggesting removing it from the list; the old value is kept.
- **Re-read (write 1 == write 2):** the written `count;` is read back as every keyword-only entry is: `ofWord('count')` under `unnamed_<n>` (in a sub-dict today, at the top level after T-079 option A). Write 2 is the same text as write 1. The in-memory form differs: after re-reading, `d.count` is gone and the entry is `d.unnamed_<n>`. Named access to keyword-only entries is T-079's option B, a maintainer choice not made here.
- **Cache round trip:** `case.save()` stores `{"_name": "count", "_value": null, "_type": "ofInt"}`; `fk load` rebuilds an `ofInt` with `.value None` (the cache sets `_value` directly, so no warning) and writes `count;`. For lists the cache loader builds `type_(value=[...])`; it must accept a `null` `_value` (test it).

## Scope
- `foamkit/types/__init__.py`: the helper, the setters listed above, `ofDict.__setattr__` (the `None` branch), the two dict writers.
- Tests: a new `tests/test_value_none.py`: one row per setter at the top level and in a sub-dict, the `d.count = None` rows, the new-key, sub-dict and list-item errors, write 1 == write 2 (top level needs T-079), the cache round trip on the pitzDaily case (`deltaT`), and constructors and cache load printing nothing.

## Out of scope
- Deleting an entry (`del d.count` already works) and the `TODO: Add method or way to delete the entries (i.e. with None)` comment in `ofDict`: `None` now means keyword-only, not delete; remove the TODO.
- Named access to re-read keyword-only entries (T-079 option B).
- `ofInt('n', None)` treats `'n'` as the value and raises a bare `ValueError` (the two-argument constructor with a `None` second argument). A constructor quirk, not an assignment; noted for the setter cleanup that follows T-086.
- `ofTable`, `ofMultilineStatement` and the `#` directive types: not value entries a user sets to `None` in practice; they keep today's behaviour (pin it).

## Acceptance criteria
- [ ] **Failing tests first:** every bold row of the table.
- [ ] Each value type above, given `.value = None` at the top level and in a sub-dict, keeps its class and key, reads `.value is None`, prints **exactly one** `WARNING:` line naming the entry, and is written `count;` (indented in a sub-dict, no padding, any comment kept).
- [ ] `d.count = None` on an existing value entry does the same and keeps the same object.
- [ ] `d.new = None` (new key), `d.sub = None` (sub-dict) and `d.l.value[0].value = None` raise `FoamKitError` naming the key or "list item"; nothing is stored or changed.
- [ ] Write → read → write: write 1 == write 2 at the top level and in a sub-dict; the re-read entry is an `ofWord` under `unnamed_<n>`.
- [ ] pitzDaily: `d.deltaT.value = None`, `case.save()`, load, write gives `deltaT;` with no warning on load.
- [ ] Constructing any type with no value, `init` → `save` → `load` of the pitzDaily case, and loading/writing every file in `tests/releases/` and `tests/fixtures/pitzDaily` print no warning and write the same text as before.
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): write an entry whose value is set to None as a keyword-only entry, with a warning (T-087)`; the commit body names the `ofList`/`ofVector` change (`None` no longer becomes `[]`/`(0 0 0)`) and the new `FoamKitError`s.

## Risks
- **Behaviour change:** `ofList.value = None` no longer empties the list and `ofVector.value = None` no longer zeros the vector on an existing entry; code reading `.value` afterwards gets `None`. `d.key = None` stops replacing the entry with Python `None` and raises for new keys. Put both in the commit body.
- **Loss by request:** `nu [dims] 1e-05;` set to `None` becomes `nu;`; the dimensions go too. The warning says the entry is now keyword-only.
- **Order:** landing before T-079 would write top-level files FoamKit cannot read back. Keep the dependency.
- **OpenFOAM versions:** keyword-only entries are read by every tested release (shipped tutorials use them: `print;`, `sphereDrag;`, `fluxRequired { p; }`); whether a given solver accepts an empty value for a given keyword is up to that solver, and the warning is the user's notice.
