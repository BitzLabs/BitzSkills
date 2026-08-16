---
id: SI-FLW-071
raised_by: FLW-REV-018（OPS-404 / OPS-203 / RVC-201 / RVC-206 / OPS-201 / BIZ-301 / BIZ-401 / BIZ-402）
target: 出荷物の記述・タスク境界の実効性・予算 SSOT の追随
proposed_change_type: modify
status: open
---
- **目的**: 「記録・反映が実装に追いつかない」型の負債をまとめて解消する。
  `FLW-REV-017` の `SYN-008` / `SYN-009` と同型であり、**是正 PR 自身が新しい実例を作った**。

- **発見した事実**:
  1. **出荷物 SKILL.md の記述漏れ**（`OPS-404`）— `UNSUPPORTED` の列挙が
     `worktree.audit` を落としており、事故対応で最初に手が伸びる診断の可用性を誤って伝える。
     `worktree.audit` 自体が出荷面で `UNSUPPORTED` のため運用者に届かない（`OPS-203`）。
  2. **遡り boundary が制約として機能しない**（`RVC-201`）— `FLW-TSK-087` / `088` / `089` の
     boundary は commit の変更集合と完全一致（17/17・15/15・17/17）で
     `git diff --name-only` の転写である。前方宣言した唯一の `FLW-TSK-090` は
     **既に2ファイルが boundary 外**であり、「事実の後付け」と判定された。
  3. **是正 PR 自身が死んだ宣言を作った**（`RVC-206`）— 実装・マージ済みの `SI-FLW-066` が
     `status: open`・本文「本 issue は**裁定待ち**」のまま残っている。
     `RVC-103`（`FLW-TSK-086` の実装不能宣言の残置）とまったく同型である。
  4. **失敗系の result が空**（`OPS-201`）— worktree write の失敗系は cause も
     `recovery_class` も `next_actions` も空で、承認再利用が「対象が既に存在する」に化ける。
  5. **予算 SSOT が未追随**（`BIZ-301` / `BIZ-401` / `BIZ-402`）—
     ROADMAP のゲート一覧が失効した判定（`FLW-REV-016` FAIL 2.85）を現在値として掲げ、
     第2次予算 5 PR / 15 session が `FLW-DSN-014` / `FLW-DSN-016` / ROADMAP へ未反映。
     M3 予算は移送された破壊系 worktree を未計上のままである。

- **提案する修正**:
  - SKILL.md の `UNSUPPORTED` 列挙へ `worktree.audit` を含める
  - boundary を**着手前に**宣言し、逸脱を機械検査する（`release_check` の WARN 等）
  - `SI-FLW-066` を裁定記録に基づき `accepted` へ遷移させ、本文の「裁定待ち」を消す
  - 失敗系 result に cause / `recovery_class` / `next_actions` を載せる
  - 予算の SSOT を1か所に定め、ROADMAP のゲート一覧を最新レビューへ追随させる

- **対象ファイル**: `plugins/bitz-flow/skills/flow-core/SKILL.md`、`flowlib/cli.py`、
  `plugins/bitz-flow/.spec/ROADMAP.md`、`.spec/design/FLW-DSN-014.md`、`.spec/design/FLW-DSN-016.md`、
  `.spec/tasks/`、`scripts/release_check.py`

- **確認観点**: boundary 逸脱が機械検査で落ちること。ROADMAP の判定値が
  最新レビューと一致すること。

- **影響推定・ロールバック**: 文書と記録が中心で、実行時の振る舞いへの影響は限定的。

- **依存**: `BIZ-402`（M3 予算の未計上）は是正では閉じず**人間の裁定**を要する。
