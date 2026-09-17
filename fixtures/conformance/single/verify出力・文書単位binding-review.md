# verify output and document-binding fixture review

Covers `SINGLE-069-01`, `SINGLE-069-02` and `SINGLE-066` from
[適合fixture仕様 §6.6](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#66-verify).
`SINGLE-068` remains open; see "The one row still missing" below.
These are reviewed expectations, not observed Core behaviour.

## The excerpt must be provably the tail

[安全な入出力・互換性 §9](../../../docs/03.詳細設計/00_共通契約/02_安全な入出力・互換性.md#9-process出力)
keeps the last 65,536 bytes of the redacted stream and sets `*Truncated` only when the raw stream
exceeded that. An excerpt made of uniform filler would satisfy a tail rule, a head rule and a
"keep everything" bug equally well, so the fixed output is marked at both ends:

- line 1 is the head marker, lines 2–1099 are filler, line 1100 is the tail marker
- every line is exactly 64 bytes, so 65,536 bytes lands on a line boundary and the expected excerpt
  needs no assumption about a split line
- 1,100 × 64 = 70,400 bytes, so the first 76 lines fall outside the excerpt

The expected excerpt therefore contains the tail marker and **not** the head marker, and the audit
asserts both. `check_excerpt_shape` additionally refuses an excerpt that is not exactly 64 KiB, and
refuses output text that collides with any redaction keyword, so redaction stays the identity here and
the expectation is not silently rewritten by a masking rule.

The audit runs each fixture's own command file and compares the produced tail byte for byte with the
committed excerpt, so this is not merely an assertion about a stream nobody generated.

`SINGLE-069-01` exits 0 and `SINGLE-069-02` exits 1. The script body is not Digest material, so both
share one Context Digest while differing in outcome — a property a regression test pins, because it
shows the Digest tracks the specification and not the run.

## `SINGLE-066`: a binding without statements

The target is a TECH that owns no normative statement and declares a document-level test.
[文書・Frontmatter・状態仕様](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)
permits a document ID in `covers` only for such a TECH, which is exactly the shape this fixture needs:
`covers: [TECH-001]`. [関係・トレースモデル §6.4](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#64-targetexpansionroot-purpose)
rule 5 makes `targetStatements` empty for a root of that kind while keeping the document-level binding.

So `targetResults[0]` reports `statements: []` together with `bindingRefs: ["root::default"]`, which is
the combination the matrix row names. The corpus keeps the TECH standalone — no relations — so the
closure is the root alone and no resolver question is left open. The audit re-parses the document and
refuses the fixture if a normative statement ever appears in it.

## The one row still missing

`SINGLE-068` (done TASK root) is deliberately still absent. Its expectation depends on a question the
normative documents do not settle: whether the documents owning a root TASK's `addresses` targets are
part of the **verify** Context.

- [関係・トレースモデル §6.2](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md#62-implement)
  states the `addresses` closure explicitly for `implement`.
- §6.3 `verify` says only "interpretに加えて対象statementのtest対応、command、実装pathを含める。
  TASKは起点指定時だけ含める。" and `interpret` never follows `addresses`.
- Yet [verify仕様 §3](../../../docs/03.詳細設計/03_操作仕様/03_verify.md#3-対象) requires a TASK target
  to verify its `addresses` targets, which is unusable if those documents are outside the Context.

The coherent reading is that they are included, but that is a normative decision, and
[適合fixture仕様 §3.3](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md#33-実成果物との対応)
forbids adding a fixture whose contract is unsettled: the expectation must arrive with the contract
change, not ahead of it. The gap is therefore reported rather than encoded.

## Limits

- No Core has run. Gate B decides agreement with Core.
- Redaction is the identity on this fixed output. The interaction between an over-limit stream and a
  redaction that lengthens the text — where `*Truncated` must still follow the *raw* size — is not
  exercised by these two fixtures.
- The excerpt boundary is exercised only on a line boundary and in ASCII, so the code-point-boundary
  rule for a multi-byte character split across the 64 KiB edge is not pinned here.
