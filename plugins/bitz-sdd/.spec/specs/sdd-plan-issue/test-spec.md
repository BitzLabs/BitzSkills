# テスト仕様書: sdd-plan / sdd-issue 新設（v1.10.0 時点）

sdd-test 工程で EARS 要件から導出した検証仕様。両要件とも verification_method は
manual-check（スキル本文の目視確認 + 機械チェック + 発動テスト）。

- 実行コマンド（機械チェック）: `python3 scripts/release_check.py` /
  `python3 scripts/spec inspect --workspace . plugins/*` / `.venv/bin/pytest`
- 最終実行: 2026-07-16 — release_check **PASS** / spec_inspect 全ワークスペース **PASS** /
  pytest **150 passed**（共有スクリプト非変更だが SDD-FR-112 に従い全スイート実行）

---

## テスト仕様: SDD-FR-120 sdd-plan スキルによる現状把握と次アクション提案

- **対象要件**: SDD-FR-120
- **EARS 節**:
  - WHEN ナビゲーション要求 THEN spec_status.py 実行 + フェーズ/ゲート判定 + 次アクション提案 SHALL
  - WHERE 決定的処理 THE 集計ロジックを持たず spec_status.py の出力のみ解釈 SHALL
  - WHILE 対話中 THE 原則ファイル非生成（STATE.md は spec_update.py 経由のみ） SHALL
  - WHEN ルーティング表参照 THEN 「現状把握・次アクション」は sdd-plan に一本化 SHALL
- **導出元種別**: Event-Driven + State-Driven（スキル規律の目視確認へ変換）
- **Verification Method**: manual-check
- **検証項目と結果**:
  - SKILL.md 目視: 実行手順①が spec_status.py 実行、②③が解釈と提案のみで集計ロジック不在 ✅ /
    「してはいけないこと」にファイル非生成・STATE.md 直接編集禁止を明記 ✅ /
    責務境界表で sdd-report と分離 ✅
  - sdd-core ルーティング表: 「現状把握・次アクション提案」行の連携スキル = sdd-plan ✅ /
    状況照会節に「解釈と提案は sdd-plan に一本化」を明記 ✅
  - skill-validator チェックリスト（A/B/C2/D1/F 機械判定）: 全項目 PASS ✅（desc 309字・65行）
  - release_check: PASS ✅
- **発動テスト（description 突合）**: 「次に何をすべきか」「現状把握」「今どのフェーズ」→ sdd-plan のみに
  トリガー語あり。「進捗を教えて」「レポートを出力して」→ sdd-report のみ（sdd-plan の description は
  「進捗」「レポート」を含まない）。語彙レベルの衝突なし ✅
- **検証ステータス**: yellow — 目視・機械チェック・description 突合は green。
  **skill-tester による実発動テスト（スキルあり/なし比較の eval 実行）が未実施**。
  完了（または人間による省略裁定）まで verified 提案を保留。

## テスト仕様: SDD-FR-121 sdd-issue スキルによる要望インテークと予備判定付き起票

- **対象要件**: SDD-FR-121
- **EARS 節**:
  - WHEN 要望の spec-issue 化要求 THEN ①分割②重複チェック③予備判定④委託先判定⑤scaffold 起票⑥裁定材料提示の順で処理 SHALL
  - WHEN 起票 THEN status は常に open・spec_inspect PASS の書式 SHALL
  - IF エージェントが裁定を試行 THEN spec_update.py の --by-human 強制で拒否 SHALL
- **導出元種別**: Event-Driven + Unwanted Behavior（権限逸脱の拒否確認）
- **Verification Method**: manual-check
- **検証項目と結果**:
  - SKILL.md 目視: インテークフロー①〜⑥を SI-CORE-017 記載の順で定義 ✅ /
    「権限分離（最重要）」節で常に open 起票・裁定は人間専用・「判定」=推薦を明記 ✅ /
    sdd-core との棲み分け（規律・ライフサイクルの正は sdd-core）を明記 ✅
  - 権限逸脱の拒否: spec_update.py の TRANSITIONS で open→accepted / open→rejected は
    human 専用（既存 pytest スイートで検証済み・150 passed に包含） ✅
  - scaffold 経由起票の spec_inspect 互換: spec_scaffold.py は PASS する雛形を生成
    （CORE-FR-011 系の既存検証で担保）。本セッションでも scaffold 起票物を含む一括 inspect PASS ✅
  - skill-validator チェックリスト（A/B/C2/D1/F 機械判定): 全項目 PASS ✅（desc 371字・73行）
  - release_check: PASS ✅
- **発動テスト（description 突合）**: 「この要望を整理して」「spec-issue にして」「起票して」「インテーク」→
  sdd-issue のみにトリガー語あり。sdd-core は「要件」「EARS」「タスク分解」等ワークフロー全体の語で、
  spec-issue インテーク固有の発話とは分離。語彙レベルの過剰競合なし ✅
- **検証ステータス**: yellow — 目視・機械チェック・description 突合は green。
  **skill-tester による実発動テスト（スキルあり/なし比較の eval 実行）が未実施**。
  完了（または人間による省略裁定）まで verified 提案を保留。
