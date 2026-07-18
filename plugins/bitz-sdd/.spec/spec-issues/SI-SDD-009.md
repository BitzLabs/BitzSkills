---
id: SI-SDD-009
raised_by: 開発フロー振り返り（2026-07-18 セッション、SI-CORE-007 実装サイクルの実地観察）
target: plugins/bitz-sdd/skills/sdd-core の統制語彙（verification_method に unit-test 相当が無い）
proposed_change_type: modify
status: accepted
---
- **目的**: テスト先行（red → green）が実装規律の標準になっているのに、verification_method の
  統制語彙（benchmark / dep-audit / example-test / load-test / manual-check / pbt / sast）に
  ユニットテスト・回帰テストを直接表す値が無く、実態は example-test を流用している
  （実例: CORE-FR-013 起票時に `unit-test` が語彙外で弾かれ example-test に振り替えた）。
  語彙と実態の乖離は、検証手段の集計・監査時に「example-test = 何を指すか」の解釈ぶれを生む。
- **提案する修正**: 次のいずれかを人間が裁定する:
  - **案A**: 統制語彙に `unit-test`（自動ユニット/回帰テストによる検証）を追加する。
    語彙の正は1箇所（spec_scaffold / spec_inspect が共有する定義）なので追加は小変更。
    既存要件の example-test は遡及変更しない
  - **案B（現状追認）**: 語彙は増やさず、example-test の定義を「実例ベースの検証
    （自動ユニット/回帰テストを含む）」と明文化する
- **対象ファイル**: 語彙定義（`plugins/bitz-sdd/skills/sdd-core/scripts/` 配下の共有定義）、
  `references/lifecycle.md` の語彙説明、`tests/`（案Aの場合は語彙追加の回帰テスト）、
  bitz-sdd マニフェスト bump。
- **確認観点**: 既存全ワークスペースの spec_inspect が引き続き PASS（後方互換）。
  案Aの場合、語彙追加が spec_scaffold / spec_inspect の両方で受理されることをテストで確認。
- **影響推定・ロールバック**: 語彙1件の追加または定義文の追記。revert で戻る。
- **依存**: なし。
- **実施**: 2026-07-18 案Aを SDD-FR-124 / SDD-TSK-010 として実装。
  `unit-test` を単一の統制語彙定義へ追加し、scaffold / inspect の回帰テストを追加。
