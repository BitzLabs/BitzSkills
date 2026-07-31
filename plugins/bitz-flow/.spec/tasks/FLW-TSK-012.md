---
implements: FLW-NFR-001, FLW-NFR-002, FLW-FR-012
depends_on: [FLW-TSK-010, FLW-TSK-011]
boundary: evals/flow-core/, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: pending
---

### M0 の3プラットフォーム eval と出口判定

- **作業内容**: FLW-DSN-014 の M0 eval protocol を実行し、結果を `evals/flow-core/` へ記録する。

  | 項目 | 固定条件 |
  |---|---|
  | platforms | Claude Code / Codex CLI / Antigravity 2.0 |
  | model record | provider、model ID、version / date を run manifest へ記録 |
  | tasks | repo inspect、dirty status、rename / binary を含む diff-summary |
  | trials | platform × task ごとに10回 |
  | prompt | version 管理した同一 prompt |
  | oracle | 最初の Git 操作が `flow.py`、schema 一致、期待 snapshot / field 一致 |
  | baseline | skill なしと v1 skill の両方 |
  | retry | agent による自己再試行は失敗。harness 再実行は別 trial |

  出口条件を判定する。platform ごとの Dispatcher Invocation Rate 95%以上かつ skill なし baseline 比
  20 ポイント以上改善、platform ごとの SFCR 90%以上（全体平均で相殺しない）、
  Cross-model Decision Parity 100%、必須 field 保持 100%、golden schema 一致 100%、
  raw fallback / 状態変更 / 秘密値出力 / 黙った truncation が各0件、
  status の median byte 削減 70%以上、diff-summary の median byte 削減 80%以上。
  operation 別の p90 と absolute byte 上限を fixture manifest へ固定する。
  出口条件を満たしたら3マニフェストの version を `0.4.0` へ bump する
  （`python3 <リポジトリ>/scripts/bump_version.py bitz-flow minor`）。
- **完了条件**: run manifest に実績 PR 数・作業 session 数・レビュー修正回数・出口未達理由が
  記録されていること。1条件でも未達なら M1 へ進まず、description・入口名・schema・renderer を
  修正して M0 を再実行すること。5回の作業 session または 1 PR で出口に到達しない場合は
  scope / pivot を人間へ再提示すること。
- **備考**: 本タスクの完了が M0 出口＝M1 の入口条件になる。version bump は M0 の PR 内に含める
  （AGENTS.md の「version bump は同一 PR 内」規約。コミット位置は問わない）。
  v2 script はこの時点でも prerelease であり、安定版入口として案内しない（FLW-DSN-011）。
