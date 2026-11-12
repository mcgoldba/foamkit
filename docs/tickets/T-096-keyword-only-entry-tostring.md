# T-096: a value-less entry's own `toString()` gives `n;` (with a warning), not `n None;`

- **Issue:** [#137](https://github.com/mcgoldba/foamkit/issues/137)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S (one keyword-only check at the top of each value type's `toString()`, sharing one helper; one fix in `ofVar`'s constructor path; no writer change)
- **Depends on:** **T-087** (#115, merged in PR #135): reuses `_isKeywordOnly` and `_keywordOnlyText`.
- **Related:** T-087 (#115; the dict writers already write `n;`), T-079 (#106; loaded `print;` entries are `ofWord`, not affected), T-076 (#103; `ofListGroups` with no groups is written `n ;`, left there), T-095 (#136; same scalar `toString()` methods, comment handling).
- **Found by:** the T-087 review (PR #135, 2026-11-12).

## Maintainer decision to confirm at approval
The maintainer (2026-11-12): the standalone `toString()` of such an entry should **either (A)** print a warning and return the keyword-only text `n;`, **or (B)** raise an error.

**Recommendation: (A).** Reasons:
- `n;` is not a guess. It is the text T-087 defined for a `None` value, and the text the dict writers already write for the same object. With (B), the same entry would write fine inside a dict but raise when written on its own.
- No data is lost. The value is `None` because the user set it (and got T-087's warning) or never gave one. The warning makes the standalone text loud too, because that call happens outside the assignment warning. The project rule asks for an error when FoamKit "can't handle a case yet". Here the case is handled exactly.
- `str(entry)` and `print(entry)` go through `toString()`. With (B) they would raise, which breaks the debugger, logging, f-strings and the `fk edit` console. Python expects `str()` not to raise.
- (B) is still possible later as an opt-in (e.g. `warnings.simplefilter('error')` if the warning becomes a Python warning category); this ticket keeps `userMsg('WARNING')` like T-087.

If the maintainer picks (B): raise `FoamKitError("Entry 'n' has no value; write it in a dictionary (as 'n;') or give it a value.")` from `toString()`. `__str__` must then not call `toString()` for such entries (return `n`), so that `print`/f-strings keep working. The silent paths below stay the same.

## Goal
A named value entry whose value is `None` gives `n;` (`n` without `ofRep`) from its own `toString()` and `str()`, with a warning naming the entry. This is the same text the dict writers give, never `None`, `$None`, `[dims] None` or a bare `TypeError`.

## Today (planner, reproduced on 3a29040 = `origin/main`, 2026-11-12)
Every entry was named `n`. Each row was checked both on the constructor without a value (`fkt.X(name='n')` / `value=None`) and after `.value = None` on an entry that had a value. "Dict writer" is `ofDictFile._entryText('n', e, True)` and `ofDict.toString`, which give `n;` wherever `_isKeywordOnly` is true. No row prints a warning from `toString()`.

| Type | `_isKeywordOnly` | `e.toString()` | `e.toString(ofRep=True)` | `str(e)` | Dict writer |
|---|---|---|---|---|---|
| `ofInt`, `ofFloat`, `ofStr` | True | **`'n           None\n'`** | **`'n           None;\n'`** | **`'n           None'`** | `n;` |
| `ofBool` | True | **`'n           \n'`** | **`'n           ;\n'`** | `'n           '` | `n;` |
| `ofVar` after `.value = None` | True | **`'n           $None\n'`** | **`'n           $None;\n'`** | **`'n           $None'`** | `n;` |
| `ofVar(name='n')` / `value=None` | **False** (stores the string `'None'`) | **`$None`** as above | **`$None;`** | **`$None`** | **`n           $None;`** (a silent invalid write inside a dict as well) |
| `ofList` after `.value = None` | True | **`'n           ()\n'`** | **`'n           ();\n'`** | **`'n           ()\n'`** | `n;` |
| `ofSplitList` after `.value = None` | True | **`'n\n(\n)\n'`** | **`'n\n(\n);\n'`** | **`'n\n(\n)\n'`** | `n;` |
| `ofListGroups` after `.value = None` | True | **bare `TypeError: 'NoneType' object is not iterable`** | same | same | `n;` |
| `ofVector` after `.value = None` | True | **bare `TypeError: 'NoneType' object is not subscriptable`** | same | same | `n;` |
| `ofUniformField` (`uniform 1.0`) after `.value = None` | True | **`'n           uniform None'`** | **`'n           uniform None;\n'`** | **`'n           uniform None'`** | `n;` |
| `ofDimensionedScalar` (`[0 2 -1 0 0 0 0] 1e-05`) after `.value = None` | True | **`'n           [0 2 -1 0 0 0 0] None'`** | **`'n           [0 2 -1 0 0 0 0] None;\n'`** | **`'n           [0 2 -1 0 0 0 0] None'`** | `n;` |
| `ofDimensionedScalar(name='n')` | True | **`'n           [0 0 0 0 0 0 0] None'`** | **`… None;\n`** | **`… None`** | `n;` |
| `ofBoundBox` after `.value = None` | True | **bare `TypeError: 'NoneType' object is not iterable`** | same | same | `n;` |

These are not keyword-only, so they are out of scope: `ofList`/`ofSplitList(name='n')` (an empty list `()`, valid), `ofVector(name='n')` (`(0.0 0.0 0.0)`), `ofBoundBox(name='n')` (`(0 0 0) (0 0 0)`), and `ofListGroups(name='n')` (`n ;` in every writer, which is T-076). `repr(e)` is the dataclass repr (`ofInt(value=None, _comment=None)`) and does not call `toString()`. Loaded `print;`/`flag;` entries are `ofWord` (T-079), not `None`-valued, so they are not affected.

Cause: only the two dict writers check `_isKeywordOnly` before calling `toString()`. The types' own `toString()` methods format `self.value` whatever it is. `ofVar`'s value setter runs `str(v)` before the `None` check, so a `None` given while the entry is built becomes the variable name `None`.

Real files: 0 (user-triggered). Users reach it through `print(d.count)`, `d.count.toString()` or an f-string after T-087's `.value = None`, and through `fkt.ofVar(name='n')` added to a dict.

## Silent paths (no warning, no raise)
The warning (or under (B) the error) fires only when the user calls `toString()` or `str()` on the entry itself. These must stay silent, and each gets a test that counts `userMsg` WARNING output:
- the dict writers `ofDict.toString`, `ofFoamFile.toString`, `ofDictFile.toString`/`_entryText`, and `case.write()`/`case.save()`. They check `_isKeywordOnly` first and must keep doing so, never calling the entry's `toString()`;
- `_fingerprint` (through `_entryText`). It also catches exceptions, so a raise there would silently turn into "changed", which is one more reason for (A);
- `str()`/`repr()` of an `ofDict` or `ofDictFile` holding the entry, and the dataclass `repr()` of the entry;
- loading (the parser builds entries through constructors, which stay silent as T-087 defined) and the `.params` cache save/load (`_toDictObj`, JSON);
- list writers: items have no name and cannot be keyword-only (T-087 raises), so they are unaffected.

## Scope
- `foamkit/types/__init__.py`: one helper (e.g. `_keywordOnlyStandalone(self, ofRep)`, which warns once per call and returns `_keywordOnlyText`), called first in `_ofNamedTypeBase.toString` and in the overrides in `ofBool`, `ofVar`, `ofList`, `ofSplitList`, `ofListGroups`, `ofVector`, `ofUniformField`, `ofDimensionedScalar` and `ofBoundBox` (only where `_isKeywordOnly(self)`). `ofVar`: a `None` given while the entry is built is stored as `None` (keyword-only, silent, like the other types), not `'None'`.
- Tests: extend `tests/test_value_none.py`, or add `tests/test_keyword_only_tostring.py`: every bold row, plus the silent paths above.

## Out of scope
- What the dict writers write (T-087 settled `n;`).
- `ofListGroups` with no groups written `n ;` (T-076), and the comment after a keyword-only entry beyond what `_keywordOnlyText` already writes (T-095).
- Turning `userMsg` warnings into a Python warning category (a separate decision for the maintainer).
- Unnamed entries (list items).

## Acceptance criteria
- [ ] **Failing tests first:** every bold cell of the table, on both the no-value constructor and `.value = None`.
- [ ] For every type in the table, a keyword-only entry gives `e.toString(ofRep=True) == 'n;\n'`, `e.toString() == 'n\n'` and `str(e) == 'n'`, and prints one `WARNING:` naming `n` and saying it is written as `n;`. No bare `TypeError`. A `//` comment is kept as `_keywordOnlyText` keeps it.
- [ ] `fkt.ofVar(name='n')` and `fkt.ofVar(name='n', value=None)` are keyword-only: `.value` reads `None`, and in a dict they write `n;`. `fkt.ofVar(name='n', value='None')` still writes `$None` (the user asked for it).
- [ ] Writing a dict or `case.write()` with a keyword-only entry, `_fingerprint`, `str(ofDict)`, `repr()`, a `.params` save and reload, and loading a file with `print;` print no warning beyond T-087's one at assignment.
- [ ] Entries with values: `toString()` output is unchanged for every type (the existing tests and goldens pass unchanged).
- [ ] `pytest -q`, ruff and mypy show no new findings against the CI ratchet baseline.
- [ ] A `fix:` PR title, e.g. `fix(types): a value-less entry prints as 'n;' with a warning, not 'n None' (T-096)`; the commit body names the changed `toString()`/`str()` text and the `ofVar` constructor change.

## Risks
- **Behaviour change:** code that parsed `str(e) == 'n None'`, or relied on `ofVar(name='n')` writing `$None`, changes. It was never valid OpenFOAM.
- **Noise:** `print(e)` in a loop warns on each call. That is accepted, because the text differs from what the user may expect. Dict writes stay silent.
- **Missed override:** a type that overrides `toString()` without the check keeps printing `None`. The tests loop over every `_isValueEntry` type, so a later type is caught too.
- **OpenFOAM versions:** none. `n;` is read by every release (T-079).
