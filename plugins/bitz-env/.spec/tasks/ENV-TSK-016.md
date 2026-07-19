---
implements: ENV-FR-013
depends_on: []
boundary: plugins/bitz-env/ 配下と evals/env-update/ のみ
status: done
---

### env-update dry-run の git 管理状態実確認と rollback 手段提示の接続

- **作業内容**: SI-ENV-025 の提案に従い、env-update の手順4（書き込み前承認フロー）と
  手順5.1（バックアップ分岐）を接続する。
  (1) SKILL.md 手順4 に、変換対象ファイルごとに git 管理状態を `git ls-files` /
  `git check-ignore` 等で実際に確認し、結果に応じた rollback 手段（管理下 = git /
  管理外 = `.bak` 取得）を対にして dry-run 提示する明示ステップを追加する
  （推測・既定値での提示を禁止）。
  (2) レジストリ `.claude/bitz-env.local.md` は env-init の既定で gitignore 対象になる旨を
  注記し、「リポジトリ内 = git 管理下」の誤推定を防ぐ。
  (3) migration-runbook.md の承認フロー節を同趣旨に同期する。
  (4) manual-check 3 観点（手順4 の対提示・手順5.1 との接続・gitignore レジストリ環境の
  机上トレース）を `evals/env-update/` に記録する。
  (5) スキル metadata version を bump（env-update）し、plugin version を bump する。
- **備考**: 契約（レジストリ書式・CORE-CON-008/009）には触れない手順の明確化のみ。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない。
