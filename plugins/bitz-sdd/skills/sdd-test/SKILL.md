---
name: sdd-test
description: BitzSDD のテスト・検証工程を行うスキル。EARS 記法の要件からテスト仕様を導出（節種別ごとの導出パターン、verification_method との対応）し、テストを実装・実行して、検証結果とトレース情報を .spec/specs/<feature>/ に記録する。ユーザーが「テストを書いて」「テスト仕様」「EARS からテスト」「検証して」「verified にして」と言及したとき、または sdd-implement の実装完了後に検証フェーズへ移行するときに使用する。
metadata:
  version: "0.1.1"
  author: br7.hide
  created: "2026-07-11"
  updated: "2026-07-16"
---

# SDD Test — EARS 要件からのテスト導出と検証

実装された要件を機械検証で充足させる工程です。「テストなき要件は存在せず、要件なきテストも存在しない」を規律とします。

## 前提

*   検証体系（L1: 仕様 / L2: コード / L3: プロセス）と verification_method の統制語彙・green 基準は
    `sdd-core` の references/verification.md が正。本スキルはそれを実行工程に落とす。
*   対象要件が `implementing`（sdd-implement のタスクに紐づけ済み）であること。

## 実行手順

1.  **テスト仕様の導出**: `references/test-derivation.md` に従い、EARS 節種別
    （Ubiquitous / Event-Driven / State-Driven / Unwanted Behavior / Optional）ごとの
    導出パターンで要件をテストケースへ変換する。verification_method との対応表に従う。
2.  **テストの実装**: テストケース名・タグに要件 ID を含める（例: `test_FR012_...`）。
    テストコードの配置はタスクの `boundary` 宣言内に収める。
3.  **記録**: テスト仕様書を `.spec/specs/<feature>/` に定型フォーマットで記録する
    （対象要件・EARS 節・導出元種別・verification_method・テストケース一覧・検証ステータス）。
4.  **実行と判定**: テストを実行し、red の場合は `sdd-core` の references/failure-protocol.md に従う
    （テストを黙って弱めない）。全 green + `spec_inspect.py` の traceability 検証 PASS で
    要件の `verified` 遷移を人間に提案する。

## 検収規律（実行範囲の最小要件）

テストの green は「実行した範囲での green」に過ぎない。検収（`done` / `verified` 提案）の前に、
変更の**影響範囲に見合った実行範囲**を確保する（sdd-implement の implementation-discipline.md 6章と同一基準。SDD-FR-112）:

*   **共有スクリプト変更時は全スイート実行**: 変更が共有スクリプト（`scripts/` 配下・プラグイン同梱スクリプト・
    複数の呼び出し元から参照される契約）に触れる場合、対象要件のテストのみの部分実行で検収を完了とせず、
    **全テストスイートの実行**を必須とする。広く参照される変更は他 fixture の回帰を招くため、実行範囲を影響範囲に合わせる。
*   **環境固有前提の不在はスキップ**: 検査が特定ファイル（例: `CLAUDE.md`）の実在を前提とする場合、
    その前提を持たない環境・fixture では不在を検査違反ではなく**スキップ**として扱う。

## 後続工程

*   verified 後の promoted 遷移（docs/ への知見還流）は Promotion Gate（`sdd-core`）が管轄する。
*   検証状況の集計は `sdd-report` が `.spec/reports/status-report.md` に自動反映する。
