---
implements: FLW-FR-013, FLW-NFR-003
depends_on: [FLW-TSK-026]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/recovery.py
status: pending
---

### recovery class決定器と許可next_actionsグラフの到達可能性検査

- **作業内容**: 失敗 result を安全に契約内へ着地させる決定器を `flowlib/recovery.py` として実装する。

  - `references/recovery-matrix.md` の表を単一の正として読み、(operation, phase, code) から
    recovery class（retry-read / reconcile-only / replan-human / human-stop）を決定する。
    **未登録 tuple・未知 field・code と cause の矛盾は例外なく `human-stop`**（fail-closed）。
  - 決定した class に対して**許可された next_actions だけ**を構築する。write の `PARTIAL` /
    `INDETERMINATE` / `STALE`、および副作用不明時は read-only の inspect / reconcile か人間停止のみとし、
    apply・代替 ref/path の補完・blind retry を構築しない。
  - **1段ではなくグラフの到達可能性を検査**する。`PARTIAL` / `STALE` / `INDETERMINATE` から
    人間の新しい裁定なしに mutation node へ到達できる next_actions グラフを不正として拒否する。
  - 安全な候補が無い場合は**空の next_actions** と `stop_reason` / `required_human_input` を返す。
  - `PENDING_INTENT` / `MUTATING` / `RECONCILING` は timeout・出力打切り・応答喪失時に必ず
    recovery matrix の行へ射影する（未分類のまま返さない）。
  - 観測 cause と postcondition を分離し、照合不能なら `INDETERMINATE` として target を
    quarantine 対象へ印付けする（再 apply 禁止）。postcondition 再照合は最大2回まで。
- **完了条件**: matrix の全行について決定器の出力が表と一致すること。到達不能と宣言された tuple が
  構築されないこと。負の対照として、mutation へ到達する next_actions グラフ・blind retry・
  未登録 tuple の暗黙 default が**すべて拒否される**ことをテストで示すこと。
  `.venv/bin/pytest -q` が全件 PASS すること。
- **備考**: 決定器は matrix を実装側へ写経せず参照する（宣言と実装の二重定義を作らない）。
  自動巻き戻し・補償は FLW-NFR-003 により禁止であり本タスクでも実装しない。
  write operation の公開は行わない。
