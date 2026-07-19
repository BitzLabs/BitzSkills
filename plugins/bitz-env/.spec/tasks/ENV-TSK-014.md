---
implements: ENV-FR-011
depends_on: []
boundary: plugins/bitz-env/ 配下と evals/env-update/ のみ
status: done
---

### env-update バージョン更新スキルとマイグレーション機構の実装

- **作業内容**: bitz-env に標準ライフサイクルスキル env-update を追加する。
  レジストリ（`.claude/bitz-env.local.md`）記録の展開時バージョン D とライブラリ版 T を比較し、
  差分のある生成物のみをマーカー区間内に限定して更新する手順を規定する。CORE-CON-009 の
  累積マイグレーション機構（`references/migrations/` のチェーン解決・連続性検査・from 昇順逐次適用・
  guard による冪等 no-op・semver 解釈不能／チェーン断裂時の安全側停止・リポジトリ外書き込みの
  dry-run + 承認）を実装する。初回出荷時 `migrations/` は空（README で規約を明示）。
  D 未記録時の扱い（安全側停止）を規定し、その前提として env-init に展開時プラグイン version の
  stamp を最小追加する。migration-steps.md の合成フィクスチャ手順で「チェーン断裂の安全側停止」
  「同一ステップ二重適用の no-op」を検証し `evals/env-update/` に記録する。plugin version を minor bump。
- **備考**: 変更境界は plugins/bitz-env/ 配下 + evals/env-update/（新規）に限る。
  実環境（リポジトリ外 ~/.claude 等）への書き込みは行わず、フィクスチャはスクラッチ領域で実施する。
