# verify fixture review (execution and pre-spawn blocks)

Covers `SINGLE-055`, `SINGLE-056`, `SINGLE-060`, `SINGLE-061`, `SINGLE-062` and `SINGLE-067` from
[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify).
Process-level vectors (`SINGLE-057`, `058`, `059`, `069-01/02`) and the multi-binding vectors
(`SINGLE-063`, `064`, `065`, `066`, `068`) are separate batches.
These are reviewed expectations, not observed Core behaviour.

## Every verify fixture stages its inputs

[verify仕様 §5.1](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#51-実行fileと環境) blocks startup
with `VERIFY-CONFIG-UNTRACKED` when the binding's workspace configuration is untracked in the index
while Git is available. The Context fixtures could use an unborn repository with nothing staged;
a verify fixture cannot, because it would never reach a command and every case would collapse onto
the same cause.

`setup.operations: [{"op": "stage", "paths": ["."]}]` is used rather than `setup.baseCommit`, because
[適合fixture仕様 §3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#3-manifest) requires a
fixture with a base commit to pass `--base`, and `verify` has no such option. The repository therefore
stays unborn with a populated index, and `revision` is `null`. The audit asserts the staging for every
case by reading the index back.

## Digest reuse

`SINGLE-055` runs against the unchanged Digest corpus, so its `targetResults[].contextDigest` is the
value `SINGLE-042` committed, not a separate constant. That ties the verify evidence to the golden.

| fixture | corpus change | `contextDigest` |
|---|---|---|
| `SINGLE-055` | none | the committed golden |
| `SINGLE-056` | command `argv` → `/bin/false` | its own value: `argv` template is Digest material |
| `SINGLE-060` | one `tests` entry removed | its own value |
| `SINGLE-061` | `command: missing` | `null` |
| `SINGLE-062` | draft REQ only | no target, so no Digest |
| `SINGLE-067` | cancelled TASK root | `null` |

`SINGLE-061` reports no Digest because
[context仕様 §6](../../../docs/03.詳細設計/03_操作仕様/01_context.md#6-context-digest) stops before
computing one when a referenced command is unfit. `SINGLE-067` reports none because a cancelled root
cannot form a Context at all. The audit enforces that a Digest is present exactly where the Context
still resolved, so the two cannot drift apart.

## Where each Diagnostic is placed

The registry's continuation unit decides this, not the status.

| fixture | condition | unit | placement |
|---|---|---|---|
| `SINGLE-060` | `CTX-COVERAGE-TEST-MUST` | `skip-target` | the target's `diagnostics` |
| `SINGLE-061` | `VERIFY-BINDING-MISSING` | `skip-target` | the target's `diagnostics` |
| `SINGLE-067` | `CTX-STATE-INAPPLICABLE` | `skip-target` | the target's `diagnostics` |
| `SINGLE-062` | `VERIFY-TARGETS-EMPTY` | `stop-operation`, source `invocation` | top level |

[verify仕様 §6](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#6-command結果) places a *binding*
Diagnostic at top level in a single workspace, but that applies to the `skip-binding` conditions
(untracked configuration, missing executable, unavailable cwd, argv limit, test outside cwd).
`VERIFY-BINDING-MISSING` is `skip-target`, so `SINGLE-061` keeps it on the target.

## Other reviewed decisions

- **`/bin/true` and `/bin/false` are the test commands.** They are deterministic, produce no output,
  and write no file, which
  [適合fixture仕様 §5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#5-副作用の検査)
  requires of a verify side-effect fixture: the command's own writes must not be confused with Core's.
  Both excerpts are therefore `""` and both truncated flags `false`.
- **`SINGLE-067` reports `statements: []`.** A cancelled root is rejected before its `addresses`
  targets are expanded, so listing the statements it would have verified would claim work that never
  happened.
- **`SINGLE-062` uses a draft REQ.** [verify仕様 §7](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#7-引数なし実行)
  targets approved REQ and approved TECH only, so a single draft document is the smallest input that
  yields zero targets without removing the workspace itself.
- **`covers` lists the statements the binding's tests cover**, and `argv` holds the expanded value
  with `{tests}` replaced by the deduplicated, sorted paths, per §5 and §8.

## Invariants the audit enforces

Beyond field equality, the audit rejects a result where `bindingRefs` and `commands[]` do not describe
the same set of executions, where a `bindingId` is not `<workspace-id>::<command-name>`, or where a
Digest appears for a Context that could not resolve. These are the properties the matrix rows name,
so they are checked as properties rather than only as literals.

## Limits

- No Core has run. Gate B decides agreement with Core.
- `SINGLE-061` names `tests[0].command` as the Diagnostic source key. The registry fixes the source
  kind as `file` but not the key; the first declaring entry is used.
- Exit codes for `/bin/false` are taken as 1, which is what the coreutils binary returns on Linux, the
  reference environment fixed for Step 0B.
