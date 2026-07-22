---
id: SI-SDD-025
raised_by: 2026-07-22 セッション冒頭の現状把握で発見（root SI-CORE-016/017/003 の恒常的な誤報告）
target: spec_status.py の accepted_unaddressed がクロスワークスペース委譲済み spec-issue を永久に未着手と誤報告する
proposed_change_type: modify
status: open
---
- **優先度（推薦）**: **中**。誤報告であり実データは壊れないが、`spec status` / `sdd-plan` の
  次アクション提案が恒常的にノイズを出し、「本当に未着手の accepted」を覆い隠す。
- **目的**: `spec_status.py` の `_accepted_issue_ids`（`accepted_unaddressed` の元）は、accepted な
  spec-issue の完了を **①本文の `- **実施**:` マーカー、または ②同一ワークスペースの origin 要件**
  でしか判定しない。ルートの spec-issue を `delegated_to` でサブワークスペースへ委譲し、**サブ側で
  要件化・実装**した場合、ルートの `spec_status` は委譲先の要件を辿れず、完了しているのに
  **永久に「accepted のまま未着手」と報告し続ける**。
  - **実害（恒常的な誤報告）**:
    | ルート spec-issue | 実体 | 現在の報告 |
    |---|---|---|
    | `SI-CORE-016` | sdd-plan 新設。PR #45 で実装・SDD-FR-120 verified | 未着手（誤） |
    | `SI-CORE-017` | sdd-issue 新設。PR #45 で実装・SDD-FR-121 verified | 未着手（誤） |
    | `SI-CORE-003` | bitz-sdd SDD-FR-001 へ要件化（本文に「要件化:」記載） | 未着手（誤） |
  - `SI-CORE-016/017` は実施マーカーも root 側 origin 要件も持たず、`003` は「要件化:」注記はあるが
    `- **実施**:` の固定書式ではないため、いずれも検出漏れになる。
- **SI-SDD-015 との関係（隣接・co-design 候補）**: `SI-SDD-015` は「**同一 WS** の origin 要件が
  verified なのに `- **実施**:` マーカーが欠落」を機械検出する提案。本 issue は「**クロスワークスペース
  委譲**により完了そのものを判定できない」で、機構が異なる（015=マーカー欠落警告の追加、
  025=誤って未着手に計上する false-positive の是正）。両者は同じ `_accepted_issue_ids` /
  `accepted_unaddressed` を触るため、**裁定・設計は同時に行うのが望ましい**。
- **提案する修正**（設計判断は Design Gate で裁定。案は排他ではない）:
  1. **委譲先を辿る**: `delegated_to: <ws>:<ID>` を持つ accepted spec-issue は、委譲先ワークスペースに
     origin が当該 issue を指す要件が存在し verified/promoted なら「対応済み」とみなす
     （`--workspace` 一括実行時のみクロス解決が可能。単体実行時は判定不能として据え置く）。
  2. **委譲マーカーの許容**: 本文に「要件化: … <ws>:<ID>」相当の固定マーカー（例 `- **委譲実施**:`）を
     設け、`_accepted_issue_ids` の除外条件に加える（クロス解決に依存しない軽量案）。
  3. データ衛生として、確認済みの `SI-CORE-016/017/003` に完了マーカーを後付けする（暫定回避。
     恒久策 1/2 とは別に人間裁定で実施可）。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_scaffold.py`（委譲マーカー書式を採る場合）、
  `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（完了記録規律）、
  `tests/test_spec_status.py`、ルート `.spec/spec-issues/SI-CORE-016/017/003`（データ後付けを採る場合）、
  bitz-sdd マニフェスト。
- **確認観点**:
  - open / accepted・マーカーあり/なし・同一WS origin あり・クロスWS 委譲済み・deprecated/superseded を
    それぞれ正しく区別すること（`_accepted_issue_ids` の回帰）。
  - 単体ワークスペース実行時にクロス解決不能でも、実装済みを誤って未着手へ戻さないこと。
  - `--impact` 集計・JSON 出力（公開契約）への変更は加算的にとどめること。
- **影響推定・ロールバック**: JSON への加算フィールド／除外条件の追加が中心でデータ移行は不要。
  データ後付け（案3）はルート `.spec` の3ファイルに `- **実施**:` を足すのみ。PR 単位で revert 可能。
- **依存**: [[verify-promotion-progress]] のクロスワークスペース委譲運用、`SI-SDD-015`（同一WS の
  マーカー欠落検出。co-arbitrate）、SI-CORE-015（`origin`/`delegated_to` 委託フィールド）、
  CORE-FR-012（未着手集計）。
- **予備判定（推薦）**: **accept 推薦**。根拠 — 恒常的な false-positive が次アクション提案の信頼性を
  下げ、本当に着手すべき accepted を覆い隠す。`SI-SDD-015` と同時に設計すれば追加コストは小さい。
  裁定は人間専用、本 issue は `open` のままとする。
