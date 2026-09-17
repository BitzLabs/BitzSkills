# done TASK root fixture review

Covers `SINGLE-068`, the last row of
[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify).
With it the verify section is complete.
This is a reviewed expectation, not observed Core behaviour.

## The contract was settled first

This fixture was held back in two earlier batches because its expectation depended on an unsettled
question: whether the documents owning a root TASK's `addresses` targets belong to the **verify**
Context. [適合fixture仕様 §3.3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#33-実成果物との対応)
forbids adding a fixture ahead of its contract, so the contract was settled first.

[関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#63-verify)
now states it directly: a TASK root brings its `addresses` targets and the documents owning them into
`contextDocuments`, the `interpret` closure rules then apply from those documents, and unlike
`implement` the root TASK's `requires` closure is **not** included.

No new decision was taken. [verify仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象)
already required a TASK target to verify its `addresses` targets, which is unusable if those documents
sit outside the Context; §6.3 simply did not say so. Two independent confirmations that this is a
completeness fix rather than a change:

1. The target-expansion reference calculation has implemented exactly this reading since the vectors
   were first reviewed, and **all 25 expected target sets are unchanged** by the edit.
2. No Diagnostic condition is added. `addresses` is a strong relation, so an unresolvable target is
   already `SPEC-RELATION-MISSING-001`; the registry's 119 conditions are untouched.

The audit noticed the edit on its own — both the Diagnostic review ledger and `targets/cases.json` pin
a hash of that document and refused to pass until the fixed expectations had been re-reviewed. The
re-review outcome is recorded in [the Diagnostic review](../Diagnostic意味網羅review.md), and only then were
the hashes re-pinned.

## The fixture

`TASK-001` is `done` and addresses `REQ-001:AC-01` only. It is the success counterpart of
`SINGLE-067`, where a cancelled root is blocked.

| | `SINGLE-067` cancelled | `SINGLE-068` done |
|---|---|---|
| status | `blocked`/2 | `passed`/0 |
| `contextDigest` | `null` | its own value |
| `statements` | `[]` | `["REQ-001:AC-01"]` |
| `bindingRefs` | `[]` | `["root::default"]` |

The Context holds three documents — the TASK root, `REQ-001` which owns the addressed statement, and
`TECH-001` which refines `REQ-001` and carries the test correspondence — so `documents[]` in the
digest input is `REQ-001, TASK-001, TECH-001` in code point order.

**`AC-02` is deliberately not addressed.** It is a statement of the same REQ, but a TASK root's targets
come from its own `addresses`, not from the owning document's full statement set. So `AC-02` is not a
target, and the test that covers it is not pulled into the binding: `tests` holds only
`tests/test_auth.py` and `covers` only `REQ-001:AC-01`. The audit rejects a result that lets either
leak in, which is what distinguishes a TASK root from the REQ root of `SINGLE-055`.

## Limits

- No Core has run. Gate B decides agreement with Core.
- The fixture pins a TASK root whose `addresses` target resolves. The non-success branch the new
  sentence also fixes — an unresolvable `addresses` target must fail the target rather than empty it —
  has no fixture in this matrix and is covered only by the existing relation-missing rows.
- The root TASK here declares no `requires`, so the clause excluding the `requires` closure under
  `verify` is stated but not discriminated by this fixture.
