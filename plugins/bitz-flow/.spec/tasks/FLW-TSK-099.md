---
implements: FLW-FR-006
depends_on: FLW-TSK-098
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py, plugins/bitz-flow/skills/flow-core/scripts/flowlib/cli.py, plugins/bitz-flow/skills/flow-core/references/operation-catalog.md, tests/test_flow_m2_runtime.py
status: pending
---

### 承認モードの配備意図を宣言から読み registry 削除を BLOCKED へ倒す

- **作業内容**: `signature_mode_status` は registry の**存在**からモードを推定するため、
  registry を削除すると承認強度が無言で `plan-digest` へ降格し `apply` が `DONE` を返して
  実 worktree を作る。閉じていたのは非敵対的な破損だけである。
  `FLW-DSN-016` §4 の改訂に従い、配備意図の宣言を鍵の実体から分離する。
  - 宣言を `<repo>/.bitz-flow/approval-mode.json`（git 追跡下）から読む。鍵の実体は
    従来どおり `$GIT_COMMON_DIR/bitz-flow-v2/trusted-worktree-keys.json`（owner-only）。
  - 判定を2値から**3値**へ改める。宣言 `signed-capability` × registry 健全 →
    `signed-capability`。宣言 `signed-capability` × registry 不在・破損・権限不正・空 →
    **`BLOCKED`**（降格しない）。宣言なし → `plan-digest`（降格ではなく素の配備）。
  - 判定が宣言より弱いモードへ動いた場合と宣言を読めない場合は、理由を `warnings` と
    `data.evidence` の**両方**へ残す。`approval_source` は実際に使ったモードを名乗る。
  - `operation-catalog.md` の承認記述を本判定へ追随させる。
- **範囲外**: 実行環境ガード（`scripts/agy_guard.py`）の是正は別タスク。責務が異なる
  （product 側の承認強度 対 測定系の保全）。
- **検証**: 宣言あり × registry の {健全 / 不在 / `chmod 644` / 空 / ディレクトリ / symlink} と
  宣言なしの各組合せに**陽性対照**を置く。`BLOCKED` になるべき組合せで `DONE` が返らないことを
  検査する。宣言ファイルが無い・壊れている場合も列挙する。**registry 削除経路のテストが
  1件も無かった**ことが指摘の中身なので、この経路のテストを必ず残す。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
