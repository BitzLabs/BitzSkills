# migrations/ — bitz-env の累積マイグレーションステップ

このディレクトリには、bitz-env が**配置先に残す状態**（レジストリ
`.claude/bitz-env.local.md`・`.claude/agents/*.md` の frontmatter・`AGENTS.md` / `CLAUDE.md` の
マーカー区間書式）の**形式変更**を跨ぐ移行ステップを置く。env-update がチェーン解決して適用する。

## 初回出荷時は空が正

現時点で bitz-env は配置先状態の形式変更を行っていないため、このディレクトリは**空（本 README
のみ）が正しい状態**である。env-update は `migrations/` に適用候補（`D < to <= T`）が無い場合、
形式変更なしとして生成物の差分更新のみを行う（CORE-CON-009 の受入基準）。

## ステップを追加するとき

**配置先状態の形式を変更する PR では、その形式変更を跨ぐステップを同じ PR に同梱する**
（書き忘れは機械検出できないため規律とする）。書式・チェーン解決・安全側停止・guard の書き方は
plugin-creator の `plugin-structure/references/migration-steps.md`（規約の正）と、本スキルの
`references/migration-runbook.md` に従う。要点のみ再掲:

- ファイル名は `<from>-to-<to>.md`（例: `0.6.0-to-0.7.0.md`）。1ファイル1ステップ。
- from/to は bitz-env **プラグイン version**（`plugin.json`、3マニフェスト共通の semver、`from < to`）。
- 必須セクション: `from` / `to` / `targets` / `transform`（before/after 例つき）/ `guard`
  （適用済み判定＝冪等性の根拠）/ `verify` / `rollback`。
- 連続チェーンにする（あるステップの `to` は次に形式が変わるステップの `from` と一致）。
  最初のステップの `from` は baseline。
- 追加したら migration-runbook.md の合成フィクスチャ手順で冪等性・安全側停止を確認し、
  結果を `evals/env-update/` に記録する。
