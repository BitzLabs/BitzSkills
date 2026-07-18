---
id: CORE-CON-009
version: 1.0
status: verified
domain: governance
priority: medium
origin: SI-CORE-028
verification_method: manual-check
derived_from: CORE-CON-008
supersedes:
superseded_by:
confidence: high
---

### CORE-CON-009 update のバージョン移行（マイグレーション）機構

- **説明**: 標準スキル `<plugin名>:update`（CORE-CON-008）の任意拡張として、プラグインが
  配置先に残す状態（配置先スキルの frontmatter `metadata` スキーマ・ワークスペースの
  `.spec` 系 frontmatter 書式・`.claude/<plugin>.local.md` 等の設定ファイル）の形式変更を、
  バージョン単位の累積マイグレーションステップで移行できるようにする。ステップは
  宣言的 Markdown（guard 条件必須）で記述し、駆動するバージョン軸はプラグイン version
  （3マニフェスト共通の semver）とする。中間バージョンのステップ欠落・チェーン断裂時は
  安全側（書き込み前に停止・提示）で振る舞う。本機構は状態の形式変更を伴うプラグインのみが
  実装すればよい任意能力であり、全プラグインへの必須要求ではない。設計の詳細は DSN-002 が正。
- **受入基準 (EARS)**:
  - THE plugin-creator は本機構の規約（ステップ書式・チェーン解決・安全側停止・skill-packager との責務境界・リポジトリ外書き込みの承認フロー）を reference として提供すること SHALL
  - WHEN プラグインがバージョンアップで配置先に残す状態の形式を変更する THEN 当該プラグインはその形式変更を跨ぐマイグレーションステップを `references/migrations/<from>-to-<to>.md`（1ファイル1ステップ、from/to はプラグイン version の semver）として同梱すること SHALL
  - THE 各マイグレーションステップは from / to / targets / transform（before/after 例つき）/ guard（適用済み判定＝冪等性の根拠）/ verify / rollback を宣言的 Markdown で記述すること SHALL
  - WHEN `update` がマイグレーションを実行する THEN 配置先の記録バージョン D からライブラリ側バージョン T までの適用候補（D < to <= T）を to 昇順で解決し、連続性検査に PASS した場合のみ from 昇順に逐次適用すること SHALL
  - IF D または T が semver として解釈不能、適用候補チェーンに断裂・欠落がある、または変換対象の入力形式を判定できない THEN `update` は書き込み前に安全側停止し、状態と不足をユーザーへ提示すること SHALL
  - WHEN 同一マイグレーションステップが同一状態に二重適用される THEN guard 条件により no-op となり状態が壊れないこと SHALL
  - WHEN マイグレーションの書き込み先がリポジトリ外である THEN dry-run の差分提示とユーザー承認の取得後にのみ書き込むこと SHALL
- **検証手段**: plugin-creator の reference（マイグレーション規約）と skill-packager
  lifecycle.md の責務境界追記を目視確認 + release_check / spec_inspect PASS
  （規定のみで既存プラグインの動作変更ゼロ。実プラグインが migrations を同梱した時点で、
  reference 記載の合成フィクスチャ手順により冪等性・安全側停止を確認する）。
- **Revision History**:
  - 1.0 (2026-07-18) 初版（draft 起票。SI-CORE-028 / DSN-002 の裁定を反映）
  - 1.0 (2026-07-18) 人間裁定により approved 化（チャット指示: 再検討のうえ問題なければ実装）
  - 1.0 (2026-07-18) implementing 遷移（CORE-TSK-015 投入）
  - 1.0 (2026-07-18) verified 遷移（CORE-TSK-015 done、release_check PASS、
    spec_inspect --workspace . plugins/* 全6ワークスペース PASS、pytest 159 green）
