---
id: SDD-FR-145
version: 1.0
status: verified
domain: workflow
priority: high
origin: SI-SDD-027
verification_method: unit-test
derived_from: SDD-FR-143
supersedes:
superseded_by:
confidence: high
---

### SDD-FR-145 人間裁定必須遷移の認可経路（対話確認・代行可視化）を規定する

- **説明**: 人間裁定必須遷移の認可経路を、対話確認経路（TTY＋完全一致再入力）と
  代行可視化経路（`--on-behalf-of`＋`--decision-ref`）の2本に規定する。代行可視化経路は
  人間の裁定の所在参照を必須として遷移を代行実行し、経路を STATE 上で対話確認と明確に
  区別して記録する。TTY は本人認証ではなく、decision-ref の真正性（当該裁定が本当に
  この遷移を許可したか）は機械検証しない — いずれも残余リスクとして明記し、検証は
  Promotion Gate の人間確認とレビューに置く。対話確認経路の詳細契約は SDD-FR-143 が正。
- **受入基準 (EARS)**:
  - WHEN 人間裁定必須遷移を要求した THEN `spec update` は対話確認経路（`--interactive-decision`）または代行可視化経路（`--on-behalf-of`）のいずれかを要求し、どちらでもない要求は対象 artifact と STATE を変更せず`authorization-required`で終了すること SHALL
  - WHEN 代行可視化経路で遷移を要求した THEN `spec update` は`--on-behalf-of`・`--decision-ref`・`--actor`の3項すべてを要求し、欠落時は対象を変更せず`authorization-required`で終了すること SHALL
  - WHEN `--on-behalf-of`または`--actor`を受理する THEN 各値を1〜128 Unicode code pointかつ改行・ASCII制御文字なしに検証すること SHALL
  - WHEN `--decision-ref`を受理する THEN 1〜512 Unicode code pointかつ制御文字なしを検証し、リポジトリ相対パス形式（任意の`#fragment`付き）では参照先ファイルの実在を必須、`https://` URL形式では形式検査のみとし、いずれにも該当しない値は`authorization-required`で終了すること SHALL
  - WHEN 代行遷移を受理した THEN STATEの構造化eventを`schema_version` 2・provenance kind `agent-proxy-unverified`・`on_behalf_of`・`decision_ref`付きで保存し、人間向け表示行に代行実行・実行者未検証・裁定参照を明示すること SHALL
  - WHEN 代行可視化経路で複数IDを1呼出しで要求した THEN workspace lockを1回取得しIDごとに独立したtransactionを直列適用し、失敗時は適用済み遷移を有効のまま停止して未適用IDと原因を診断へ列挙し、同一呼出しのevent群は同じ`decision_ref`を共有すること SHALL
  - WHEN `spec inspect`が`schema_version` 2のeventを検査する THEN provenance kind別の必須フィールドを検査し、`schema_version` 1のeventは従来どおり受理し、パス形式`decision_ref`の参照先消失はWARNとして報告すること SHALL
  - WHEN `spec status`または`sdd report`が人間裁定必須遷移を集計する THEN 経路別（対話確認 / 代行）に分離して集計すること SHALL
- **検証手段**: `tests/test_spec_update.py`（経路の排他、3項欠落拒否、decision-ref 検証、
  バッチ fail-fast と decision_ref 共有）、`tests/test_spec_transaction.py`（schema v2 event）、
  `tests/test_spec_inspect.py`（v1/v2 併存受理、kind 別必須フィールド、参照先消失 WARN）で
  unit-test する。共有スクリプト変更のため全 pytest と release check を実行する。
- **Revision History**:
  - 1.0 (2026-07-27) 初版（draft 起票）。SI-SDD-027 の accepted 裁定と
    SDD-DSN-005 v2.0 Design Gate 承認（裁定点1〜7）から導出。
