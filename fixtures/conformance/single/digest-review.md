# Context Digest fixture review

Covers `SINGLE-042`, `SINGLE-043-01/02`, `SINGLE-044-01/02`, `SINGLE-045`.
`SINGLE-042` owns the single-workspace golden Canonical JSON and Digest
([適合fixture仕様 §4](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#4-共通normalizer)).
These are reviewed expectations, not observed Core behaviour.

## Shared corpus

One fixed corpus is copied into each fixture; nothing is shared by symlink or parent reference.

| path | role |
|---|---|
| `.spec/bitz.yaml` | `schemaVersion`/`language`/`earsAi` plus one `default` command with a `{tests}` template |
| `.spec/requirements/REQ-001.md` | root. `AC-01` MUST/ALWAYS/CONSTRAINT, `AC-02` SHOULD/WHEN/THEN with `[REASON]` |
| `.spec/technical/TECH-001.md` | `refines: [REQ-001]`, `related: [ADR-001]`, two `implements`, two `tests`, `x-owners` |
| `.spec/decisions/ADR-001.md` | target of a weak relation only |
| `src/*.py`, `tests/*.py` | declared `implements` and `tests[].path` must exist as regular files |

## Reviewed decisions

1. **purpose is `verify`.** Only `verify` names `command` in its closure
   ([関係・トレースモデル §6.3](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#63-verify)),
   so it is the purpose that populates `settings.commands` and `settings.verifyTimeouts` — the
   richest digest settings material. §6.6 verify fixtures also carry per-target Digests, so the
   golden is computed under the purpose those fixtures will reuse.
2. **`addressed` is empty and `unaddressed` holds every target statement.** Under `verify` no TASK
   enters the closure, so nothing `addresses` the targets. `CTX-COVERAGE-TASK-*` is registered for
   `purpose=implement` only
   ([Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)),
   so a non-empty `unaddressed` raises no Diagnostic here and the status stays `passed`.
   Both targets are tested, so `CTX-COVERAGE-TEST-*` does not apply either.
3. **No extensions anywhere.** Core 1.0 loads no Profile Manifest, so every extension namespace is
   unknown and would return `EAI-EXT-UNKNOWN-001`/warning, which cannot coexist with the matrix's
   `passed`/0. `statements[].extensions` is therefore `[]` in every fixture, and the extension
   sort rule of
   [Digest正規化 §3.1.3](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#313-statements)
   is **not** exercised by this family. It needs a fixture whose expected status tolerates a warning.
4. **Unborn repository, `revision: null`.** `context` has no `--base` option, and a fixture with
   `setup.baseCommit` must pass `--base`, so a Digest fixture cannot hold a base commit. The Digest
   does not take `revision` as material, so this does not weaken the golden.
5. **`activation.text` is `null` for `ALWAYS` in the digest input, and absent from the result.**
   Digest input may not create optional keys
   ([§5](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#5-serializationとhash)),
   while `result.schema.json` requires `activation.text` to be a non-empty string when present.
   The two representations differ deliberately.
6. **Result `frontmatter` carries declared fields only; digest `frontmatter` fills all fixed keys.**
   [context仕様 §5](../../../docs/03.詳細設計/03_操作仕様/01_context.md#5-projection) presents the
   allowed declared fields, while
   [Digest正規化 §3.1.1](../../../docs/03.詳細設計/00_共通契約/03_Context-Digest正規化仕様.md#311-frontmatterのprojection)
   fixes five relation keys and empty arrays. `x-owners` appears in neither: Core does not use `x-`
   for Context, which is exactly what `SINGLE-045` pins.
7. **`reachedBy` for `TECH-001` is `refines:TECH-001`.** The document is reached by traversing its own
   `refines` edge backwards from the root, and §5 defines the token as `<relation>:<source-id>`,
   where the source of that edge is `TECH-001`.
8. **`TECH-001` is projected `full`.** `standard` projects distance-1 documents as `full`
   (context仕様 §5), so `--detail full` in `SINGLE-043-01` changes only `projection.detail` and
   `--expand TECH-001` in `SINGLE-043-02` changes only `projection.expanded`. Both leave `documents[]`
   and the Digest untouched, which is the property the matrix asks for.

## Two independent reference computations

Gate A requires the golden to agree across two independent reference computations.

| reference | source of the digest input | serializer |
|---|---|---|
| A (`digest_reference.py`) | reviewed literals | recursive string builder, keys sorted by UTF-16BE bytes |
| B (`digest_crosscheck.py`) | the fixture's own `repo/` tree | streaming byte emitter, keys sorted by explicit code-unit lists |

B imports none of A's literals. It re-reads `bitz.yaml` and the Markdown documents with a narrow
reader for this corpus shape, recovers Frontmatter, normalises the body, parses the statements, and
applies the dedup/sort rules itself. The audit runs B against a freshly built repository twice per
fixture and compares the bytes with A and with the committed
`expected/context.canonical.json`.

Writing B independently found a real defect in it: the statement pattern accepted `[MUST] [REASON]`,
which the EBNF allows only for `[SHOULD]`. B now rejects it, and a regression test pins that.

## Limits

- No Core has run. Every expectation is reviewed, not observed; Gate B decides agreement with Core.
- B is scoped to this corpus. It refuses a strong edge outside the reviewed closure rather than
  generalising, so it is not a target-expansion implementation.
- The federation golden (`MONO-002-01`) is still missing, so the federation half of the Gate A
  Digest condition remains open.
- Equality across `SINGLE-042/043/045` is checked as Canonical JSON bytes, not only as hash strings,
  so a serializer change cannot hide behind a matching hash.

## 2026-09-17: reason、full projection、versionの専用fixture

`SINGLE-101-01`、`SINGLE-106-01`、`SINGLE-121`は既存golden corpusを使用する。
理由付きSHOULDはREQの第2句に存在し、LedgerのreasonとCanonical JSON内の全statementを
固定する。fullは`--detail full`を明示し、各文書の必須fieldと禁止fieldを結果Schemaで検証する。
versionはCanonical JSONのdigestVersionとresolverVersionがともに1.0であることを固定する。
いずれも入力、manifest、完全期待JSON、Canonical JSON、副作用snapshotを保持し、
独立2系統の計算と2回の隔離setupを既存goldenと同じ検証へ通す。
reason除去、fullへのexpandable追加・bodyText欠落、両version改変を拒否する回帰検査を追加した。
Core実行や出力観測は含まない。

## 2026-09-17: 内部Parser受入とescape・normative

ユーザー裁定により、公開context Schemaへsourceを追加せず、完全IRの比較を内部Parser受入へ分離した。
適合fixture仕様 §4.1とmanifestのparserChecksが入力path・期待JSONを固定する。
Step 0Bではreview済み値を入力byte列と照合し、Step 2のGate Bでは実Parserから得た
全IRを比較する。fixture referenceを呼ぶだけでCore受入とはしない。

- SINGLE-097-01: 5種類の既知escapeを1行で検査する。reference Aは解除後textを明示した
  literal、reference Bは入力から左→右のescape解除を行う。完全IRはline 15/16、column 3、
  raw候補行、source path、全意味fieldを固定し、公開JSONとCanonical JSONは従来どおり完全比較する。
- SINGLE-101-01: 同じ内部受入を追加し、理由付きSHOULDの全IRを固定する。
- SINGLE-106-02: TECH-001をrefineする距離2のTECH-002を追加する。statementやtestを増やさず、
  documentCountだけが3となる。TECH-002のprojectionはnormative、statementRefsは空配列、
  frontmatter/bodyText/expandableは省略する。新文書を含むDigestは2系統の計算で照合する。

source位置、raw、解除後text、reasonの改変、normativeへのbodyText追加とstatementRefs欠落、
Parser期待値の不存在・path逸脱・重複を拒否する。新しいreference readerはcode spanを
未対応のまま受理せず、専用vectorの確定を要求する。
