# Explicit-report fixture review

Covers `SINGLE-071-01/02/03/04` and `SINGLE-072` from
[適合fixture仕様 §6.7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#67-出力とreport).
These are reviewed expectations, not observed Core behaviour.

## The side-effect schema had to grow

Until now every fixture was `policy: "read-only"` with `before == after`, which cannot express a run
that legitimately creates a file. `side-effects.schema.json` now takes `policy: "explicit-report"`
with a `report` object, and the schema pairs the two: `explicit-report` requires `report`, and
`read-only` forbids it.

Report file names carry a generation time and a sequence
([結果・Diagnostic・終了コード §8](../../../docs/03.詳細設計/00_共通契約/01_結果・Diagnostic・終了コード.md#8-report)),
and the common normalizer excludes exactly that, so the created file cannot be named in a snapshot.
`before` and `after` therefore describe only the paths that already existed — all of which must be
unchanged — and the `report` object carries the delta: the directory, the created count, the name
pattern, and that no temporary file remains.

```json
{"directory": ".spec/reports", "createdCount": 1,
 "namePattern": "^[0-9]{8}T[0-9]{6}Z-(?:check|verify)(?:-[1-9][0-9]*)?\\.json$",
 "temporaryFilesRemaining": 0}
```

The audit does not take the pattern on trust: it requires the pattern to accept a well-formed name and
to reject a missing timestamp, a zero sequence, a different operation and a leftover `.tmp` suffix.
A fixture that relaxed its pattern to `^.*$` is rejected.

## Exclusive creation needs something to collide with

Each `SINGLE-071-*` corpus keeps the `.spec/reports/existing.json` introduced by the no-report group.
Creating a report into an empty directory would not distinguish exclusive creation from replacement;
with a pre-existing report present, `before == after` means the old report survived untouched while
`createdCount: 1` means a new one appeared beside it. The audit refuses a fixture whose snapshot lost
that file.

The four cases cover both operations on both outcomes, and reuse the reviewed results of the
`SINGLE-070-*` pair directly: saving a report does not change the result that was already computed,
so restating it would only create a way for the two groups to drift.

## `SINGLE-072` is based on the failing check, deliberately

The matrix asks that an unusable destination still return "元結果" to the terminal. Built on the
*passing* check, that property would be vacuous — there would be no original Diagnostic to preserve.
It is therefore built on `SINGLE-070-02`, whose result already carries
`SPEC-RELATION-MISSING-001`. The expectation is that the result body is unchanged, the original
Diagnostic survives, `SPEC-REPORT-WRITE-001` is appended, and the status rises from `failed` to
`error`. The audit compares against the source fixture field by field and refuses a source that has no
Diagnostics of its own.

**The destination is blocked by a regular file, not by a directory mode.** Git does not record
directory permissions, so a `0o555` report directory would not survive a fresh checkout and the fixture
would silently stop testing anything. Placing a regular file at `.spec/reports` is version-controllable
and makes the directory unusable for the same reason. The audit asserts the file is still a file after
setup, and that the `SINGLE-071-*` fixtures still have a real directory.

## Limits

- No Core has run. Gate B decides agreement with Core, including that the created file is the result
  JSON and that creation is genuinely exclusive under a same-second collision.
- The sequence suffix is accepted by the pattern but no fixture produces one; a same-second collision
  needs two runs, which a single-invocation fixture cannot express.
- `SINGLE-072` pins one way for a destination to be unusable. A read-only directory, a full filesystem
  and a permission error are not separated by this matrix.
