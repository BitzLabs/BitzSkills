---
implements: FLW-NFR-014
depends_on: [FLW-TSK-115]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_runtime.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_operability.py,tests/test_flow_m2_platform_probe.py,tests/test_flow_m2_platform_adapter.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: done
---

### 実環境platform probeを実装しproduction経路へ結線する

`SI-FLW-084`（`FLW-REV-027:SYN-001` P0）。`FLW-DSN-017` §13.1が記録するとおり、
`PlatformObservation`を構築するproductionコードが存在しない。

- **実測した欠陥**:
  - `worktree_platform.py`に実測probe（`uname`／`statfs`／`GetVolumeInformationW`等）が
    1つも無く、`evaluate_platform()`の呼出元は`tests/`だけである。
  - `worktree_runtime.plan()`は`platform_evidence is None`のとき
    `WorktreeRuntimeError("platform evidence is required")`を送出する（L255-L256）。
    productionからevidenceを渡す経路が無いため、**公開集合へ戻しただけでは必ず例外で停止する**。
  - `worktree_operability.py` L237は`"platform_support": "requires-runtime-evidence"`を
    返しており、doctorも実証跡を持たない。
- **作業内容**:
  - `worktree_platform.probe_platform()`を追加する。**read-only**で、owner、filesystem
    type／class、非追随walk、native component、case semantics、OS lock、file／directory
    durability、child supervisionを観測する。
  - OS別の実装: linuxは`/proc/self/mountinfo`をst_devで引く。macOSは`statfs(2)`の
    `f_fstypename`をctypesで取る。Windowsは`GetVolumeInformationW`をctypesで取る。
  - 観測不能・未知・networkは`supported`へ格上げせず`UNSUPPORTED_FILESYSTEM`へ閉じる。
    probeは例外を送出せず、理由をclosed evidenceの`reasons`へ載せる。
  - `plan()`の既定を「probeで生成」に変える。evidence非対応は例外ではなく
    closed resultへ写す。
  - doctorを同じ生成器へ結線し、`requires-runtime-evidence`の自己申告を実測結果へ置換する。
- **完了条件**:
  - `plan()`が`platform_evidence`未指定でも例外を送出せず、supported環境では
    plan生成、非supported環境では`UNSUPPORTED_FILESYSTEM`へ閉じること。
  - doctorとplanが同一のevidence生成器を使うこと（機械検査）。
  - 実行中OSでの**実観測**testがgreenであること。他OSは分類ロジックの構造test
    （実観測ではないと明示する）。
  - network／未知filesystem／観測不能をsupportedへ格上げしないこと。
  - `FLW-DSN-017` §13.5の「実観測」欄を実測結果へ更新すること。
- **見積り**: 実装PR 1本・1〜2 session。
- **実行判定**: `FLW-TSK-115`（legacy除去）の後に行う。旧context参照を残したまま結線すると
  `worktree_dir_guard_key`のAttributeErrorが顕在化する。
  worktree operationの公開集合はgatedのまま維持する。
