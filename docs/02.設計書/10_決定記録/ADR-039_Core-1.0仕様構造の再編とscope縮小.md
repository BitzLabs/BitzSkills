---
id: ADR-039
title: Core 1.0仕様構造の再編とscope縮小
status: accepted
relations:
  requires:
    - ADR-009
    - ADR-010
    - ADR-021
    - ADR-025
  supersedes:
    - ADR-015
    - ADR-017
    - ADR-030
    - ADR-038
  related:
    - ADR-014
    - ADR-016
    - ADR-018
    - ADR-026
    - ADR-027
---

# ADR-039 Core 1.0仕様構造の再編とscope縮小

## Context

Core 1.0の設計は、EARS-AI、単一workspaceのSPEC、型付き依存、Context、静的検査、実行検証を中心に開始した。
レビューで契約の欠落を解消する過程で、モノレポ連合、ID衝突の自動改番支援、将来Profile、4種類の公開hash、
必須改訂履歴、厳格な本文スタイル、内容同一性によるverify binding重複排除が追加された。

各判断は個別には成立するが、同じ契約を設計書、詳細設計、ユースケース、運用、ADRへ再掲したため、
変更時の同期範囲が広がった。主要な操作仕様2文書だけで980行あり、Core 1.0の価値を実証する前に拡張同士の
相互作用まで実装しなければならない状態になった。

構造化設計、KISS、YAGNI、DRYの観点から、中心的な垂直スライスを残したまま規範の所有者とscopeを縮小する。
検討と採決事項は提案11に記録した。

## Decision

1. 規範の所有者を共通契約、EARS-AI言語、SPEC文書モデル、Context解決モデル、操作仕様、SDDフローへ分ける。
   Schema field、状態遷移、Diagnostic効果、対象選択規則は1つの正本だけが定義する。
2. ADRは判断理由と代替案を保持する非規範の履歴とする。現行契約はADRを読まずに実装できなければならず、
   規範本文から「ADRを正とする」と参照しない。
3. `check`と`verify`を独立した操作仕様へ分割する。ID、関係、path、coverageは共有トレースモデルが所有する。
4. Contextの型付き関係、適用可能性、完全閉包、coverageを共有モデルへ置き、`context`操作仕様は入力、提示、
   Context Digest、stale検出、結果を所有する。
5. Core 1.0は単一Git repository内の単一workspaceを対象とする。`monorepo.members`、修飾ID、横断所有、
   `--all-workspaces`、モノレポCapabilityを1.1以降へ延期する。結果のworkspace IDは`root`に固定する。
6. Core 1.0は現在集合の重複IDを`failed`にするが、勝敗判定、自動改番候補、`idCollisions`、
   `SPEC-BASE-AMBIGUOUS-001`、専用`Integrate`段階を提供しない。人間が改番し通常checkで確認する。
7. Core Parserは名前空間付き拡張をopaqueな値として保持する。Profile Manifest、外部Validator、
   Profile固有Serializer／migration、Profile互換性判定を1.1以降へ延期する。SDD、Quality、DDDの案は
   非規範の将来候補とする。
8. SPEC本文の`Revision History`をCore必須項目から外す。正確な差分、変更者、時刻はGitを正とし、重要な理由は
   ADR、PR、commit、または任意の`Notes`へ記録する。ADRディレクトリのローカルな記載規則は維持してよい。
9. 公開hashはstale検出用の`contextDigest`だけとし、`semanticHash`、`fileHash`、`projectionDigest`は
   公開Schemaから除く。実装は内部cache keyとして任意の内容hashを使ってよい。
10. verify bindingはcommand名で識別する。同じcommand名に属するtest pathを重複排除して1回実行する。
    異なるcommand名はargvとcwdが同じでも別bindingとして実行する。
11. Coreの本文構造検査はFrontmatter、H1、EARS-AI配置、REQの`Intent`、`Acceptance Criteria`、
    `Verification`へ限定する。H2順序、空の任意節、太字疑似節はテンプレート・任意linterの責務とする。
12. 実装ロードマップは規範設計から分離し、提案・計画資料として扱う。
13. EARS-AI安定ID、候補Scanner、型付き依存の完全閉包、`MUST`句単位coverage、承認済みREQ保護、
    未信頼入力、test processのtimeoutと出力上限、`failed`／`blocked`／`error`の区別は維持する。

## Consequences

- Core 1.0の実装対象は、単一workspaceにおける`context -> check -> verify`の垂直スライスへ縮小される。
- 仕様の変更理由が異なる機能は別文書となり、操作固有の変更が他操作の再レビューを要求しにくくなる。
- モノレポ利用者はCore 1.0ではGit repository rootの単一`.spec/`を使用する。複数`.spec/`の連合はできない。
- 並行branchのID衝突はmerge/rebase後の重複checkで検出し、人間が参照を含めて改番する。
- 改訂履歴の短い要約を各SPECだけで確認する機能は失われる。Git log、PR、ADRを使用する。
- 表示内容そのものの公開digestはなくなり、Core 1.0が保証するのは仕様解釈のstale検出だけになる。
- 同一argvを別command名で定義した場合は2回実行される。command名が利用者の実行意図を表す。
- 旧ADRは判断履歴として残るが、現行実装の入力にはしない。

## Alternatives

1. **現行仕様をそのまま実装する**: 既に契約は詳細化されているが、中心価値の実証前に横断機能を一括実装する
   必要があり、変更コストが高いため採用しない。
2. **文書だけ分割しscopeを維持する**: 発見性は改善するが、相互作用とfixture数は減らないため採用しない。
3. **公開操作を`context`と`check`だけに縮小する**: 実行テストまでの垂直価値を検証できないため採用しない。
4. **モノレポとID改番だけ維持する**: 両機能は互いにworkspace修飾、基準版、集約Schemaへ波及するため、
   単一workspace実証後にまとめて再評価する。
5. **すべてのhashを維持する**: 表示再現性とcache観測性は得られるが、Core 1.0の安全判定に必要なのは
   Context Digestだけであるため採用しない。

## Notes

- 本ADRはADR-015、ADR-017、ADR-030、ADR-038を文書全体として置換する。
- ADR-014のSemantic IRと段階的Projectionは維持するが、Projection Digestの公開だけをDecision 9で変更する。
- ADR-018のProfile予約Schemaは現行Core 1.0から外す。名前空間付き拡張を失わず保持する判断は維持する。
- ADR-026のtimeoutとcommand結果Schemaは維持するが、binding同一性と公開Digest構成はDecision 9、10で変更する。
- 再評価条件は提案11のS1〜S7を参照する。
- Decision 5のモノレポ延期、対応するConsequences、および本項の再導入条件は
  [ADR-040](ADR-040_モノレポSPEC連合をCore-1.0へ再導入する.md)で置き換えられた。Decision 1〜4、6〜13と、
  モノレポ以外のscope縮小は変更しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-01 | 仕様責務を再編し、Core 1.0を単一workspaceの垂直スライスへ縮小 | 提案11 |
| 2026-09-02 | Decision 5のモノレポ延期を部分改訂 | ADR-040 |
