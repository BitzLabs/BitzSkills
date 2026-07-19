---
implements: ENV-FR-012
depends_on: []
boundary: plugins/bitz-env/ 配下と evals/env-update/ のみ
status: done
---

### stamp 後付け救済（env-doctor 検出 + env-update 救済フロー）の実装

- **作業内容**: ENV-DSN-002 の設計に従い、bitz-env-version 未記録環境の救済パスを実装する。
  (1) env-doctor の診断項目に「レジストリ存在・`bitz-env-version` 不在」の WARN 検出と
  env-update 救済フローへの誘導を追加する（読み取り専用維持）。
  (2) env-update の安全側停止条件 (b) を救済フローへの分岐に改訂する: D を保守的に最古側へ
  推定（migrations/ 最古ステップの from。ステップ不在時は差分更新のみ）し、推定値・根拠・
  適用内容を提示 → ユーザー承認後、適用の最初に推定 D を stamp → 以降 ENV-FR-011 正常系へ
  収束。レジストリ不在時は env-init 案内で停止。migration-runbook.md の文言も同期する。
  (3) 合成フィクスチャによる manual-check 4 観点を `evals/env-update/` に記録する。
  (4) スキル metadata version を bump（env-doctor / env-update）し、plugin version を minor bump。
- **備考**: 変更境界は plugins/bitz-env/ 配下 + evals/env-update/ に限る。実環境
  （リポジトリ外 ~/.claude 等）への書き込みは行わず、フィクスチャはスクラッチ領域で実施する。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
