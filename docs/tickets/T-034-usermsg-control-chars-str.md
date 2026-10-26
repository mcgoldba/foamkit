# T-034: `userMsg` escapes C1 and bidi control characters; `str(FoamKitError)` never raises

- **Issue:** [#45](https://github.com/mcgoldba/foamkit/issues/45)
- **Type:** code (owner: `tester` first, then `implementer`)
- **Size:** S
- **Follows:** T-025. Found in the round-3 review on PR #36.

## Goal
A message containing untrusted case-file text cannot change how the terminal displays it, and turning a `FoamKitError` into a string never fails.

## Findings (T-025 round-3 review, PR #36)
- `userMsg` translates C0 controls and DEL through `_CONTROL_CHAR_TABLE` (`foamkit/__init__.py`), but **not C1 controls `\x80`–`\x9f`**. Some terminals treat these as control sequences, for example `\x9b` (CSI).
- **Bidi override and isolate characters** U+202A–U+202E and U+2066–U+2069 pass through. They can reorder how a message is displayed (a "Trojan Source"-style risk). This part is optional, but recommended.
- **Pre-existing bug:** `FoamKitError.__str__` returns `self.msg`. When `msg` is not a `str` (for example `FoamKitError(42)` or `None`), `str(err)` raises `TypeError`.

## Scope
- Add `\x80`–`\x9f` to `_CONTROL_CHAR_TABLE`, written as `\\xNN` like the C0 entries.
- Optionally add U+202A–U+202E and U+2066–U+2069, written as `\\u202e` and so on. The implementer includes them unless the reviewer objects. Record the decision in the PR.
- `FoamKitError.__str__` returns `str(self.msg)`.

## Out of scope
- Other Unicode (normal non-ASCII text such as accented names must print unchanged)
- Messages written by the logger at DEBUG level

## Acceptance criteria
- [ ] **Failing tests first:** at each level, a message containing `\x9b`, `\x85`, `‮` and `⁦` is printed with each character escaped visibly. `FoamKitError(42)`, `FoamKitError(None)` and `FoamKitError(Path("x"))` make `str()` raise `TypeError` today.
- [ ] After the fix, those characters print escaped. `str(FoamKitError(42)) == "42"`, and `.msg` is unchanged (still the original object).
- [ ] Normal non-ASCII text (`"Größe é 日本"`) prints unchanged (a regression test).
- [ ] All T-025 tests still pass unchanged.
- [ ] `pytest -q` passes. `ruff` and `mypy foamkit/` show no new findings compared with the CI ratchet baseline.
- [ ] A `fix:` commit whose body describes the user-visible change.

## Risks
- **Escaping bidi characters changes the display of legitimate right-to-left text.** Only the override and isolate controls are escaped, not RTL letters.

## Ranking rationale
After T-023. It is small and reduces risk, but the inventory shows no real case file containing these characters. The load failures come first.
