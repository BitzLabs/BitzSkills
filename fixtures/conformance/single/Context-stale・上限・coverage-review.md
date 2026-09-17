# Non-success Context and coverage fixture review

Covers `SINGLE-046`, `SINGLE-047`, `SINGLE-048-01/02`, `SINGLE-049` and `SINGLE-054`,
completing [適合fixture仕様 §6.5](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#65-contextとdigest).
These are reviewed expectations, not observed Core behaviour.

## Two rules applied across the group

1. **A non-success Context delivers no Bundle material.**
   `documents`, `constraintLedger.statements` and `coverage` stay empty for every non-success
   fixture. `stop-operation` is defined as "操作全体を停止する"
   ([Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)), and
   [context仕様 §7](../../../docs/03.詳細設計/03_操作仕様/01_context.md#7-stale検出) requires that a
   stale Context is not implicitly accepted. Withholding the Bundle is the safety side: an adapter
   that ignored `status` still cannot consume the material. `CTX-LIMIT-001` says so outright
   ("部分Bundleを返さない"), and the same shape is applied to the others rather than inventing a
   per-code rule.
2. **`contextDigest` is non-null exactly when complete resolution held.**
   [Digest正規化 §2](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#2-全体手順)
   step 1 forbids computing a Digest without complete resolution, so `resolution.complete` and the
   presence of a Digest are the same fact reported twice. The audit enforces that they cannot
   disagree.

| fixture | `complete` | `documentCount` | `contextDigest` |
|---|:--:|--:|---|
| `SINGLE-046` stale | true | 2 | the committed golden of `SINGLE-042` |
| `SINGLE-047` expand outside the set | true | 2 | the committed golden of `SINGLE-042` |
| `SINGLE-048-01/02` closure limits | false | 0 | `null` |
| `SINGLE-049` presentation hard limit | true | 4 | its own computed value |

`SINGLE-046` and `SINGLE-047` reuse the Digest corpus unchanged, so their reported Digest is the
value `SINGLE-042` committed rather than a separately invented constant. A regression test pins that.

## Per-fixture decisions

- **`SINGLE-046`** passes `--expect-digest sha256:00…0`. The source is `invocation` with
  `argument: "--expect-digest"`, matching the registry's `invocation` source for `CTX-DIGEST-STALE`.
  The caller learns the current value by re-running without the option; the refusal does not carry
  the Bundle.
- **`SINGLE-047`** expands `ADR-001`, a document that exists in the workspace but is outside the
  closure — `related` does not expand the closure. That is a sharper vector than a non-existent ID,
  because it also pins "依存へ追加しない": `documentCount` stays 2 and `projection.expanded` is `[]`.
- **`SINGLE-048-01/02`** place the limit in configuration rather than in bulk input.
  `context.maxDocuments` accepts 1–100 and `context.maxBytes` 4,096–1,048,576
  ([workspace・設定仕様](../../../docs/03.詳細設計/02_SPECモデル/01_workspace・設定仕様.md)), so
  `maxDocuments: 1` against a 2-document closure and `maxBytes: 4096` against a 4,776-byte
  presentation cross the configured limit exactly once each. The audit recomputes both margins from
  the fixture's own bytes, so padding cannot silently stop crossing the limit.
- **`SINGLE-049`** is the only fixture that must cross a *fixed* limit: the presentation hard limit
  is 1 MiB regardless of configuration. Both closure dimensions are configured at their maxima so the
  closure passes, and the corpus is a refinement chain `REQ-001 ← TECH-001 ← TECH-002 ← TECH-003`
  in which only the two indirect refinements are large. At `standard` those are projected
  `normative` and contribute no `bodyText`
  ([context仕様 §5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-projection)), so the
  measured quantity — "ContextのSemantic IRと標準提示"
  ([安全な入出力・互換性 §4](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#4-resource上限)) —
  stays small, while `--detail full` would present 1,071,063 bytes of body. Each file stays under the
  1 MiB single-document input limit.
- **`projection.detail` echoes the requested mode; `projection.expanded` lists what was actually
  applied.** `SINGLE-049` therefore reports `detail: "full"` with `expanded: []`, and `SINGLE-047`
  reports `detail: "standard"` with `expanded: []`.
- **`SINGLE-054`** is the only success-status fixture here, so it is the only one with a full Bundle
  and a Digest of its own. `TASK-001` addresses `AC-02` only, leaving the MUST `AC-01` unaddressed:
  exactly one `CTX-COVERAGE-TASK-001` warning, and all five coverage buckets are non-trivially
  populated across `must` and `should`. The audit checks that `addressed`/`unaddressed` and
  `tested`/`untested` each partition `total`.

## implement is a different digest input

`SINGLE-054` runs `--purpose implement`, and the matrix requires its Digest to be its own value.
[関係・トレースモデル §6.2](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#62-implement)
lists `implements`, test correspondence and TASK `changes` in the implement closure but does **not**
name `command`, which only §6.3 `verify` does. So `settings.commands` and `settings.verifyTimeouts`
are empty under `implement`, while the addressing TASK joins `documents`. `purpose` is itself digest
material, so the two canonical forms cannot collide; a regression test asserts they differ.

Reference B was extended for this group and both extensions were real gaps in B, not restatements:
it now reads `context.maxDocuments`/`maxBytes` from the workspace configuration instead of assuming
the defaults, and it follows the transitive refinement chain rather than only direct refiners of the
root. It still refuses any strong edge its reviewed rule cannot account for.

## Limits

- No Core has run. Gate B decides agreement with Core.
- The presentation byte measure is taken as body text of presented documents. If Core counts the
  serialized Bundle instead, `SINGLE-049` keeps its verdict — the margin is over 20 KiB — but the
  exact threshold case is not pinned by this fixture.
- `SINGLE-048-01/02` name the root document as the Diagnostic source. The registry fixes the source
  *kind* as `file` but not which file; the root is the closure's origin.
