---
implements: FLW-NFR-001
depends_on: [FLW-TSK-009]
boundary: evals/flow-core/fixtures/v2-skill/
status: done
---

### M0 v2 flow-core SKILL.md（eval fixture）の Mandatory entry protocol

- **作業内容**: FLW-DSN-010 のスキル構成に従い、v2 の `flow-core` SKILL.md を
  `evals/flow-core/fixtures/v2-skill/SKILL.md` として作成する（2026-07-31 裁定により
  稼働中の SKILL.md は M0〜M5 の間 v1 のまま据え置く）。本文は次の順序へ固定する。

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
- **備考**: 稼働中の `plugins/bitz-flow/skills/flow-core/SKILL.md` を本タスクで変更しない
  （boundary 外）。v1-current を M0 の時点で壊さないための分離であり、稼働ファイルへの反映は
  FLW-DSN-011 の切替シーケンス手順9（v1 撤去）と同じ変更セットで行う。
  Promotion Gate では、稼働 SKILL.md が eval で測定した fixture と同一内容であることを
  照合する（fixture と稼働ファイルの乖離検出）。
  裁定参照: `.spec/reports/decision-2026-07-31-m0-skill-fixture-separation.md`。
