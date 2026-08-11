---
id: FLW-NFR-010
version: 1.0
status: verified
domain: verification
priority: high
origin: SI-FLW-035
verification_method: unit-test
derived_from:
supersedes:
superseded_by:
confidence: high
---

### FLW-NFR-010 platform固有の測定不能署名をfail-closedに分類する

- **説明**: M0評価runnerは、platform固有の構造化拒否イベントと実行痕跡を組み合わせて
  「被測定物が一度も評価されなかったtrial」を測定不能として分類し、通常失敗へ混入させない。
- **受入基準 (EARS)**:
  - WHEN Claude Code event streamが`rate_limit_event.rate_limit_info.status == rejected`を含み、
    command・tool・token使用の実行痕跡が無い THEN harnessは当該trialを`agent_unavailable: true`、
    `measurable: false`としてharness再試行の対象にすること SHALL
  - WHEN Claude Code resultが`subtype: success`かつ`is_error: true`でsession limitを示すが、
    構造化拒否イベントまたは実行痕跡の条件が揃わない THEN harnessは文言一致だけで
    `agent_unavailable`を真にしないこと SHALL
  - WHEN Codex CLIまたはAntigravityが各platformの構造化された容量・rate limit拒否を返し、
    実行痕跡が無い THEN各runnerは同じ共通observation契約で測定不能を記録すること SHALL
  - WHEN command・tool・token使用のいずれかの実行痕跡がある THEN harnessはrate limit関連文言が
    応答に含まれても当該trialを`agent_unavailable`として除外しないこと SHALL
  - WHEN trialを記録する THEN runnerは再導出に必要なraw event logをrun manifestから解決可能な
    永続pathへ保存し、そのdigestを採点履歴で追跡できること SHALL
- **検証手段**: `tests/test_m0_eval_scoring.py`で3platformの拒否署名、Claudeの矛盾した
  `subtype`/`is_error`、実行痕跡によるfalse positive防止、raw log永続pathをunit testする。
- **Revision History**:
  - 1.0 (2026-08-11) 初版（draft 起票）
  - 1.0 (2026-08-11) SI-FLW-035のaccept裁定に基づき、platform固有署名とraw log証跡の
    fail-closed契約を具体化。
  - 1.0 (2026-08-11) ユーザー承認。裁定記録:
    `.spec/reports/decision-2026-08-11-si-flw-035-agent-unavailable.md`
  - 1.0 (2026-08-11) 着手前照合で構造化署名判定の一部先行実装を確認。要件趣旨は維持し、
    専用回帰とraw log既定永続化を残作業として限定した。
