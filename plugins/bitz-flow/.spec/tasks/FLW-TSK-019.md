---
implements: FLW-NFR-001, FLW-FR-003
depends_on: FLW-TSK-012
boundary: evals/flow-core/m0-eval/run_codex.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/result.py, plugins/bitz-flow/skills/flow-core/schemas/result-v1.schema.json, plugins/bitz-flow/skills/flow-core/references/output-contract.md, evals/flow-core/fixtures/v2-skill/SKILL.md, tests/test_flow_contract.py
status: done
---

### SI-FLW-014 / SI-FLW-015 の裁定を実装し測定不能への対策を強化する

- **作業内容**: 第7ラウンドで判明した3件の裁定を実装する
  （裁定記録 `.spec/reports/decision-2026-08-06-si-flw-014-015-012-batch.md`）。

  | 対象 | 変更 |
  |---|---|
  | `SI-FLW-014` | `_task_output` が match を集める際に `--help` / `-h` を含む実行を落とす。除外した実行は `observation.help_invocations` へ残す |
  | `SI-FLW-012` 再検討 | `--harness-retries` の既定を 2 → **5** へ。位置依存のため回数だけでは収束しないことを help 文へ明記 |
  | `SI-FLW-015` | `paginate()` の戻り値と compact の `TRUNCATED` 行から `cursor` を落とす。schema・契約文書・v2 SKILL.md も揃える |

- **完了条件**:
  1. `--help` を実行した trial で、その直前の正しい実行が採点対象になること
  2. `--help` **しか**実行しなかった trial は従来どおり失敗として扱われること
  3. `TRUNCATED` 行と JSON の `page` から `cursor` が消え、`shown` / `total` で打ち切りが可視であること
  4. 打ち切られた残りが `--limit` を大きくして取り直せること（回復経路の固定）

- **検証結果**:
  - `_task_output` の単体確認 — 正しい実行と `--help` が混在する場合は前者が採点対象になり、
    `--help` のみの場合は `('', False)`（失敗）を返すことを確認した
  - `flow.py git status --limit 2` の compact 出力が `TRUNCATED shown=2 total=33`
    （`cursor=` なし）、JSON の `data.page` が `{'shown': 2, 'total': 33}` になることを確認した
  - `tests/test_flow_contract.py` に `cursor` 不在の検査（2 箇所）と
    `test_truncated_items_are_reachable_by_limit`（`--limit` による回復経路）を追加した

- **備考**: `first_git_action` の判定は変更していない。`--help` であっても「生 git ではなく
  `flow.py` を選んだ」ことは事実であり、入口遵守の観点では成功として数えてよい（裁定どおり）。
  `--base HEAD~1` のような比較元の誤りは引き続き失敗として数える。
  未使用になった `_compact_cursor()` は削除した。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
