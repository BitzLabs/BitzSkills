---
implements: FLW-NFR-001, FLW-NFR-002, FLW-FR-012
depends_on: [FLW-TSK-010, FLW-TSK-011]
boundary: evals/flow-core/m0-eval/, plugins/bitz-flow/.claude-plugin/plugin.json, plugins/bitz-flow/plugin.json, plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
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
  | baseline | skill なしと v1 skill の両方（v1 = 稼働中の SKILL.md、v2 = `evals/flow-core/fixtures/v2-skill/`） |
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
- **進捗（2026-08-03, 第2ラウンド）**: 修正後の Claude Code 90 trial を実測。設計修正の効果は明確で、
  Invocation 100% / SFCR 100% / 必須 field 保持 100% / golden schema 100% / 危険事象 0件 /
  `diff-summary` byte 削減 89.0% と、**`dirty-status` を除く全指標が閾値を超えた**
  （第1ラウンドは SFCR 67% / field 44% / diff 62%）。
  残る未達は `dirty-status` の byte 削減 5.9%（閾値 70%）のみ。no-skill の Claude Code は
  `git status --porcelain=v1` を選ぶ（raw log で確認）ため、compact と同じ1項目1行形式が分母になり
  **現行の測定法では原理的に達成できない**。閾値変更は要件変更のため `FLW-NFR-002` の supersede を
  spec-issue へ起票して人間裁定を仰ぐ。codex-cli / antigravity は第2ラウンド未実測。
- **進捗（2026-08-03, 第1ラウンド）**: 270 trial を実測したが、**出口 FAIL かつ結果は証跡にならない**。
  未達の大半が harness 欠陥に由来し、スキル設計を測れていないため。欠陥2件を修正した
  （agy の `--sandbox=false`、全 harness へ `--keep-logs`）が、agy 側は Gemini のクォータ上限により
  **実機未検証**。設計側の論点2件も `FLW-DSN-010` の許す手段で修正済み
  （`diff-summary` の `--base` 既定を HEAD 化 + `NEXT` へ base 明示、v2 SKILL.md の
  `--format json` 誘導を compact 既定へ是正）。効果の確認は再実測待ち。
  詳細は `evals/flow-core/m0-eval/README.md` の現況節。
  version bump は未実施のまま（3マニフェストと `flowlib/__init__.py` は `0.3.1`）。
- **進捗（2026-07-31）**: harness（`evals/flow-core/m0-eval/`）まで実装済み、**実測は未実施**。
  3platform × 3条件 × 3task × 10 trial の実行は別途行う。したがって version bump も未実施で、
  3マニフェストと `flowlib/__init__.py` の `__version__` は `0.3.1` のまま揃えている
  （出口条件を満たした時点で同じ変更セットで 0.4.0 へ上げる）。
  harness の予備計測で **byte 削減率が閾値未達**（`dirty-status` 63% / 70%、
  `diff-summary` 66% / 80%）であることが判明した。数値を通すための fixture 差し替えや
  baseline の弱体化は行っていない。実測開始前に (1) baseline コマンドの定義、
  (2) fixture の代表性、(3) 閾値そのものの再校正を人間が裁定する必要がある
  （詳細と実測値は `evals/flow-core/m0-eval/README.md` の予備計測節）。
