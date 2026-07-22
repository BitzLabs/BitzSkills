---
id: SDD-FR-142
version: 1.0
status: verified
domain: reporting
priority: medium
origin: SI-SDD-015
verification_method: example-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-142 spec_status による実施記録欠落の機械警告

- **説明**: SI-SDD-005 で spec-issue の完了記録を `- **実施**:` マーカーに統一したが、accepted
  spec-issue の origin 要件が verified / promoted へ到達しても本文にマーカーが無いと、
  `spec_status.py` は origin 参照により「未着手ではない」と正しく判定する一方、spec-issue 単体を
  読んでも実装根拠・PR・検証済み要件を辿れない（実例: SI-FLW-001、ルート SI-CORE-016/017/003）。
  手順明文化だけでは記録漏れが再発するため、本要件は origin 参照で対応済みと判定された accepted
  spec-issue のうち、参照元要件の status が verified / promoted かつ本文に `- **実施**:` マーカーが
  無いものを、新規フィールド `completion_record_missing` として集計し警告する（読み取り専用。
  自動追記はしない。新しい status・新しいマーカー語彙は追加しない）。
- **受入基準 (EARS)**:
  - WHEN accepted spec-issue の ID を実行スコープ内のいずれかの workspace の要件 `origin:` が参照し、
    その参照元要件の status が verified または promoted であり、かつ当該 spec-issue 本文に
    `- **実施**:` で始まる行が無い THEN その spec-issue を `completion_record_missing` に計上すること SHALL
  - WHEN origin 参照元要件の status が verified / promoted 未満（draft / approved / implementing 等）
    THEN 実施マーカーの有無に関わらず `completion_record_missing` に含めないこと SHALL
  - WHEN 当該 spec-issue 本文に `- **実施**:` マーカーがある THEN origin 要件の status に関わらず
    `completion_record_missing` に含めないこと SHALL
  - WHEN `completion_record_missing` が1件以上存在する THEN 人間向けテキスト出力・`next_actions`
    双方に、件数と修正候補（対象 spec-issue ID・参照要件 ID・status）および
    「`- **実施**:`（参照要件 ID・PR 等）を追記する」旨を含めること SHALL
  - WHEN `--json` を指定して実行する THEN JSON 出力に `completion_record_missing`（ID 一覧）を
    含む新規フィールドを追加すること SHALL
  - THEN 本機能は `accepted_unaddressed` の判定・件数を変更しないこと SHALL（別フィールド・別警告）
  - THEN 本機能も `.spec/` 配下への書き込みを一切行わず、自動追記もしないこと SHALL（読み取り専用）
- **検証手段**: `tests/test_spec_status.py` に fixture（origin 参照あり・要件 verified・マーカー
  なし／要件 draft・マーカーなし／要件 verified・マーカーあり）を追加し、`completion_record_missing`
  の計上・除外・JSON フィールド・テキスト/next_actions 文言を検証する。加えて本リポジトリで
  データ後付け前に SI-CORE-016/017/003 相当が検出されることを確認する（example-test）。
- **Revision History**:
  - 1.0 (2026-07-22) 初版（draft 起票）。origin: SI-SDD-015。設計は SDD-DSN-004
