---
id: SI-FLW-040
raised_by: M1-3およびM1-4着手時の実装者（claude）
target: FLW-FR-004・FLW-CON-002（M0でverified済み）／M1以降のタスク分解
proposed_change_type: modify
status: accepted
---
- **目的**: **M0 で verified になった要件のうち、適用範囲が M1 以降で広がるもの**を、
  ライフサイクルの規律を壊さずに実装へ結び付ける方法を裁定する。
  現状では該当タスクを起票できず、M1-4 の一部が着手不能である。

- **現状（機械的に詰んでいる）**:

  | 要件 | status | M0 で検証した範囲 | M1 で増える範囲 |
  |---|---|---|---|
  | `FLW-FR-004` Git 読み取りと工程別診断 | verified | `git.status` / `git.diff-summary` | `diff-detail` / `log` / `branches` / `conflicts` / `worktree.list` / `fetch` |
  | `FLW-CON-002` Operation Contract と副作用上限 | verified | read operation | write operation（concurrency key・partial・Recovery ID） |

  どちらも**要件本文はもともと M1 の範囲を含んでいる**が、M0 では read 部分だけを検証して
  verified にした。M1 のタスクから `implements` すると `spec_inspect` が
  「verified/promoted だが未完了 local task がある」で FAIL する。
  `spec update <ws> FLW-FR-004 --to implementing` は
  `ERROR [precondition-failed]: 不正遷移: verified -> implementing` で拒否される
  （ライフサイクルに `verified → implementing` の戻り経路が無いため）。

- **これまでの回避**: `FLW-CON-002` は M1-1（`FLW-TSK-026`）で `implements` から外し、
  本文参照に切り替えて備考に「M1-3 分解時に spec-issue を起票する」と記録した。
  `FLW-FR-004` は M1-4 の「残る Git read」タスクにとって**唯一の該当要件**であり、
  同じ回避ができない（`implements` が空になる）。

- **提案する選択肢**:

  | 案 | 内容 | 影響 |
  |---|---|---|
  | **A（推奨）** | M1 スコープの新要件を起票し、M0 verified 分は範囲を明示して据え置く | bitz-flow 内で完結。要件 ID が増える |
  | B | ライフサイクルに `verified → implementing` の戻り経路を追加する | bitz-sdd の変更。全ワークスペースへ波及 |
  | C | 既存要件を milestone ごとに分割する | `implementing 以降の EARS は書き換え不可` の不変条件に抵触 |
  | D | verified 判定に milestone スコープを持たせる | 検証証跡・Gate の設計変更が要る |

  A を推奨する理由: 影響が bitz-flow に閉じ、既存の verified 判定と検証証跡を無効化しない。
  「M0 で検証した範囲」と「M1 で検証する範囲」が別要件として台帳に残るため、
  Promotion Gate での検分もしやすい。

- **対象ファイル**: `.spec/requirements/FLW-FR-004.md`、`.spec/requirements/FLW-CON-002.md`、
  A を採る場合は新規要件ファイル、`.spec/tasks/FLW-TSK-042.md` ほか M1-4 のタスク。

- **確認観点**: 裁定後に `python3 scripts/spec inspect --workspace . plugins/*` が
  全ワークスペース PASS になること。M0 の検証証跡（`.spec/verification/`）を無効化しないこと。

- **影響推定・ロールバック**: 裁定までは M1-4 の「残る Git read」（`FLW-TSK-042`）と
  contract 全行検証（`FLW-TSK-046`）の一部が着手できない。write 側（fetch / sync / publish / doctor）は
  `FLW-FR-005` / `FLW-FR-011` / `FLW-CON-005` / `FLW-CON-006` で表現でき、影響を受けない。

- **依存**: `SI-FLW-039`（write_state 表記ゆれ）とは独立。
