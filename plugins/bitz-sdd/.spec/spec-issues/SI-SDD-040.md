---
id: SI-SDD-040
raised_by: bitz-flow M1-4（SI-FLW-040 の委託）
target: sdd-core の TRANSITIONS・references/lifecycle.md・遷移テスト
proposed_change_type: modify
status: accepted
---
- **目的**: **verified になった要件の適用範囲が後続の作業で広がったとき**に、
  検証証跡を壊さずに実装へ結び付けられるようにする。現状は機械的に詰んでおり、
  該当タスクを起票できない。

- **現状**: ライフサイクルは
  `draft → approved → implementing → verified → promoted` の一方向で、
  `implementing → approved`（中断で戻る）はあるが **`verified → implementing` が無い**。
  そのため次の状態になる。

  - verified 要件を新しいタスクの `implements` に書くと、`spec_inspect` が
    「verified/promoted だが未完了 local task がある」で **FAIL** する
  - `spec update <ws> <ID> --to implementing` は
    `ERROR [precondition-failed]: 不正遷移: verified -> implementing` で拒否される

- **実際に詰まった例**（bitz-flow / `SI-FLW-040`）:

  | 要件 | M0 で検証した範囲 | 後続で増える範囲 |
  |---|---|---|
  | `FLW-FR-004` Git 読み取り | `git.status` / `git.diff-summary` | `diff-detail` / `log` / `branches` / `conflicts` / `worktree.list` / `fetch` |
  | `FLW-CON-002` Operation Contract | read operation | write operation |

  どちらも要件本文はもともと後続範囲を含むが、先行 milestone では一部だけを検証して
  verified にした。`FLW-CON-002` は `implements` から外して回避したが、
  `FLW-FR-004` は該当タスクにとって唯一の要件であり回避できない。

- **提案する修正**: `TRANSITIONS["requirement"]` に `("verified", "implementing")` を追加する。
  ただし**無条件に開くと verified の意味が薄れる**ため、次の歯止めを併せて入れる。

  1. **実行権限は `human`** とする。機械が勝手に verified を取り消せないようにする。
     人間裁定必須遷移と同じく `--interactive-decision` か `--on-behalf-of` の経路を要求する。
  2. **理由の記録を必須**にする。STATE には遷移の provenance に加え、
     「なぜ再着手するのか」を裁定参照（`--decision-ref`）で残す。
  3. **既存の検証証跡を無効化しない**。`.spec/verification/` の記録は残し、
     再び verified になるときに新しい証跡が追加される（過去の証跡を削除・改変しない）。
  4. `promoted` からの戻りは**追加しない**。Promotion Gate を通ったものは
     deprecated 経由でのみ変更する（現行のまま）。

- **対象ファイル**:
  - `plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py`（`TRANSITIONS`、人間裁定必須集合）
  - `plugins/bitz-sdd/skills/sdd-core/references/lifecycle.md`（状態遷移図と遷移表）
  - `tests/test_spec_update.py` 系の遷移テスト

- **確認観点**: `verified → implementing` が人間裁定経路なしでは拒否されること。
  裁定参照つきなら遷移し、STATE に記録が残ること。`promoted → implementing` は
  引き続き拒否されること。既存の verified → promoted / deprecated が壊れないこと。
  `python3 scripts/spec inspect --workspace . plugins/*` が全ワークスペース PASS のままであること。

- **影響推定・ロールバック**: 全ワークスペースへ波及する。ロールバックは
  `TRANSITIONS` から該当行を除くだけで足りるが、その時点で戻り遷移を使った要件があれば
  status を手当てする必要がある。

- **依存**: bitz-flow `SI-FLW-040`（裁定記録:
  `plugins/bitz-flow/.spec/reports/decision-2026-08-12-verified-requirement-rescope.md`）。
