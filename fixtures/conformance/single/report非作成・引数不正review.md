# Report-absence and argument-error fixture review

Covers `SINGLE-070-01/02/03/04` and `SINGLE-073-01/02`, `SINGLE-074-01/02/03` from
[適合fixture仕様 §6.7](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#67-出力とreport).
These are reviewed expectations, not observed Core behaviour.

## An existing report makes immutability testable

The matrix asks for "file生成0件、既存report不変". A corpus with no report can only demonstrate the
first half: a run that silently rewrote an existing report would still show zero *new* files. Every
`SINGLE-070-*` corpus therefore already holds `.spec/reports/existing.json`, and the audit refuses a
fixture whose snapshot lacks it, so the immutability half cannot quietly become untested.

The four cases cover both operations on both outcomes, because "does it write without `--report`" is
a different question on a failing run than on a passing one:

| fixture | operation | status |
|---|---|---|
| `SINGLE-070-01` | `check --full --base HEAD` | `passed`/0 |
| `SINGLE-070-02` | `check --full --base HEAD` | `failed`/1 |
| `SINGLE-070-03` | `verify REQ-001` | `passed`/0 |
| `SINGLE-070-04` | `verify REQ-001` | `failed`/1 |

The two verify cases reuse the reviewed results of `SINGLE-055` and `SINGLE-056` directly rather than
restating them. The added report file is not SPEC material, so the Context and its Digest are
unchanged, and importing the result keeps the two groups from drifting apart.

The check cases count three documents and two statements: `REQ-001` with its two statements, `TECH-001`,
and `ADR-001`. That matches the existing convention, where an ADR is a checked document contributing no
statements. `SINGLE-070-02` fails through a single cause — `TECH-001` requires a missing `TECH-999` —
which is the same `SPEC-RELATION-MISSING-001` shape already reviewed in the trace batch.

The check group uses a base commit and passes `--base HEAD` as the fixture contract requires, while the
verify group stages instead, because `verify` has no `--base` and blocks on an untracked configuration.

## Argument errors produce no result at all

`expect` for all five carries no `status` and no `resultFile`, which the manifest contract allows only
when the invocation returns no common result. The audit rejects a manifest that adds either.

| fixture | invocation | rejected because |
|---|---|---|
| `SINGLE-073-01` | `context REQ-001 --report` | only `check` and `verify` accept `--report` |
| `SINGLE-073-02` | `doctor --report` | same |
| `SINGLE-074-01` | `check REQ-001 --full` | `--full` and an explicit target are exclusive |
| `SINGLE-074-02` | `verify src/auth.py` | a code path is not a verify target |
| `SINGLE-074-03` | `check REQ-1` | fewer than three digits is not a document ID |

`SINGLE-074-03` is deliberately a *lexical* error rather than an absent ID.
[CLI基盤契約 §6](../../../docs/03.詳細設計/00_共通契約/06_Core実行環境・CLI基盤契約.md#6-targetとworkspaceの不存在)
separates the two: a syntactically valid but absent ID starts the operation and returns
`CTX-ROOT-MISSING-001`/failed, while an ill-formed one never starts it. `REQ-1` fails the
`[0-9]{3,}` rule, so it can only be the second.

## One stderr contract, now operation-aware

The stderr expectation lived in the Git-environment batch and was hard-wired to `bitz: check: `.
Rather than copy it, `check_cli_error_output` now takes the operation, so all five fixtures and the
earlier one share a single statement of the contract: exit 4, empty stdout, exactly one line, a
non-empty reason, and no terminal control characters. Each fixture's `cli-output.json` records its own
prefix, and the audit exercises the helper on that operation, rejecting a wrong prefix, an empty
reason, a second line and a non-4 exit code.

## Limits

- No Core has run. Gate B decides agreement with Core.
- The reason text after the prefix is deliberately unconstrained; only its presence and safety are
  fixed, so wording changes do not break the matrix.
- `SINGLE-074-01` pins one exclusive pair. The other exclusions in the public syntax — around
  `--all-workspaces` — are not covered by this fixture.
