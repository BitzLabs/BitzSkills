---
implements: FLW-NFR-001
depends_on: [FLW-TSK-009]
boundary: plugins/bitz-flow/skills/flow-core/SKILL.md
status: blocked
---

### M0 flow-core SKILL.md の Mandatory entry protocol

- **作業内容**: FLW-DSN-010 のスキル構成に従い、`flow-core/SKILL.md` の本文を次の順序へ固定する。

  1. Mandatory entry protocol — Git / GitHub 操作は `flow.py` を使う。raw fallback をしない。
     `UNSUPPORTED` なら停止して不足操作を報告する。
  2. Intent routing — ユーザー意図を domain / action へ写像する短い表。
  3. Plan / apply rule — mutation は plan → 必要な外部裁定 → apply → post-check。
     operation ID は人間承認の証明ではない。
  4. Stop conditions — stale / blocked / unavailable / partial / indeterminate の扱い。
  5. References routing — 必要な workflow reference だけを読む。

  本文に通常経路の生 `git` / `gh` 例を置かず、dispatcher の command 例だけを置く。
  目標は 100〜150 行以内。description には git・gh・branch・commit・diff・worktree・Issue・PR・
  merge・CI・release・CHANGELOG と「上記操作を行う前に必ず発動」「生 CLI の代わりに同梱
  dispatcher を実行」を明記する。「開発」のような一般語だけでは発動させない。
  dispatcher discovery は SKILL.md 自身の directory を基準に `./scripts/flow.py` を示し、
  repo へ script をコピーしない。初回 action はローカル Git 読取なら `repo inspect` とする。
  `next_actions` は許可された domain / action と必要引数だけを返し、shell 文字列を返さない。
- **完了条件**: FLW-DSN-010 の機械検査項目（禁止 raw command block の不在、public invocation が
  `flow.py` だけ、`UNSUPPORTED` 時の fallback 禁止の明記）を満たすこと。
  skill-validator のチェックリストを通過すること。
- **備考**: **着手前に人間の確認が必要**（`status: blocked`）。FLW-DSN-011 は Promotion Gate まで
  v1-current（現行4スキル）を実行契約とし「v2 script を安定版入口として案内しない」と定めるが、
  Mandatory entry protocol は「必ず `flow.py` を使う」と宣言するもので、稼働中の
  `flow-core/SKILL.md` を M0 時点で置き換えると v1-current の案内が失われる。
  一方 FLW-DSN-014 の M0 eval は skill なし・v1 skill・v2 skill の3条件を比較するため、
  同一時点で v1 と v2 の両方が必要になる。
  FLW-DSN-011 の canary が M0 cohort を「3platform の保存 fixture」と表現していることから、
  v2 SKILL.md を eval fixture として分離し、稼働中の SKILL.md は Promotion Gate で切り替える
  解釈を第一候補とする。稼働ファイルを直接書き換える解釈を採る場合は boundary と
  v1-current の定義が変わるため、着手前に裁定する。
