---
implements: FLW-FR-003, FLW-NFR-001
depends_on: FLW-TSK-012
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/references/output-contract.md, evals/flow-core/fixtures/v2-skill/SKILL.md, tests/test_flow_contract.py
status: done
---

### SI-FLW-011 の裁定に基づき NEXT の snapshot 添付を同一 operation に限定する

- **作業内容**: `SI-FLW-011` の裁定（accept・案1）に基づき、`NEXT` が `snapshot` を載せるのを
  「次の操作が現在の操作と同じとき」に限定する。

  | 箇所 | 変更 |
  |---|---|
  | `cli.py` `repo.inspect` → `git.status` | `snapshot` を落とす（別 operation） |
  | `cli.py` `git.status` → `git.diff-summary` | `snapshot` を落とす（別 operation） |
  | `cli.py` `git.status` → `git.status`（ページング） | **温存**（同一 operation） |
  | `cli.py` `git.diff-summary` → `git.diff-summary`（ページング） | **温存**（同一 operation） |

  併せて `references/output-contract.md` へ「snapshot は operation 固有であり別 operation へ
  引き渡してはならない」「`NEXT` が載せるのは同一 operation のときだけ」「`STALE` からの回復は
  `--snapshot` を外して同じ operation を呼び直す」を明記し、compact 例の `NEXT` 行を実態へ合わせる。
  `evals/flow-core/fixtures/v2-skill/SKILL.md` の同じ例も修正する。

- **完了条件**: `tests/test_flow_contract.py` に次の3つを追加し、緑であること。

  1. `NEXT` が示した引数をそのまま渡すと成功する（連鎖を辿って全 invocation が exit 0）
  2. `NEXT` の `snapshot` 添付が「同一 operation のときだけ」という不変条件を満たす
  3. 同一 operation へ食い違う `snapshot` を渡せば `STALE`（exit 6）を返す＝楽観ロックを失わない

- **備考**: 既存の `test_compact_line_order` は `NEXT` 行に `snapshot=` があることを表明しており、
  **不具合側の挙動を固定していた**ため裁定に合わせて是正した（`base=HEAD` の存在と
  `snapshot=` の不在を検査する形へ）。
  裁定記録は `.spec/reports/decision-2026-08-06-si-flw-011-next-snapshot.md`。
  効果の確認（codex-cli の SFCR 回復）は M0 eval の再実測で行うため本タスクには含めない。
  本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
