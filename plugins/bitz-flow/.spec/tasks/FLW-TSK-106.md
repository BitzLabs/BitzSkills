---
implements: FLW-NFR-014
depends_on: []
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_capability.py,plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_promotion.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2,tests/test_flow_m2_contract_v2.py
status: implementing
---

### capability v2 schemaとminimum-runtime promotion契約を固定する

- **作業内容**: `FLW-DSN-017` §2・§6・「影響範囲・ロールバック」を実装契約へ固定する。
  - capability、binding、lease、counter、intention、postcondition、receipt、namespace manifestの
    `schema_version: 2` JSON Schemaを`additionalProperties: false`で定義する。
  - `approval_declaration_digest`をcapability署名payloadの必須fieldとし、v1、欠落、未知field、
    context不一致を既定値補完せず`BLOCKED`にする。
  - canonical JSON、NFC、case-sensitivity discriminator、platform別file identityを固定し、
    accept/reject canonical vectorを作る。
  - `FLW-DSN-017` §6.3のschema inventoryで本タスク所有recordだけを`active`としてruntime codecとの
    双方向round-tripを証明し、後続タスク所有recordはproducer禁止の`reserved`にする。
  - owner-only・非追随・atomic replace/fsyncのminimum-runtime sentinelとpromotion preflightを実装し、
    配布policy、実filesystem/registry列挙、実process probeでsupported entrypoint inventoryを証明できない
    環境ではcontract v2 stateを生成しない。
- **完了条件**: active schemaとruntime codecのfield・round-tripが双方向一致し、reserved schemaから
  producerが生成されず、旧runtime・旧capability・未知field・NFD・platform別identity異常・entrypoint
  残存/差替えの各陽性対照がfail-closed、正常な3platform実entrypoint fixtureがpromotion可能になる。
- **実行判定**: 契約固定タスク。設計裁定済みのため実装は機械的だが公開契約を扱う。利用可能な
  下位tier委譲先が確認できない場合は司令塔が自己実行し、契約差分を発見したら中断してspec-issueへ戻す。
- **実装・検証記録（2026-08-22）**:
  - capability v2 の strict parser、9個の閉じた JSON Schema、owner-only・非 symlink・
    atomic replace/fsync の minimum-runtime sentinel、3 entrypoint の promotion preflight を実装。
  - 対象 schema 契約: `11 passed`。
  - M2 runtime 回帰: `79 passed`。
  - 全体 pytest: `2139 passed, 1 failed`。唯一の失敗は
    `test_active_manifest_records_real_three_platform_run` の compatibility fingerprint 不一致。
  - その後のユーザー裁定で3者 confirmation を実走。qualification は3者とも PASS。
    confirmation は2試行とも Claude / Codex が `206 tests`・runtime `69/69`・hazard 0・
    residual 0でPASSしたが、Antigravity は初回がpre-tool hook拒否によるFAIL、許容された
    1回の再試行が `TimeoutExpired`（240.393秒）でBLOCKED。合成はBLOCKEDのため
    active manifestを更新せず、本タスクは `implementing` を維持する。
  - `spec_inspect --workspace . plugins/* --check-only`: 全8 workspace PASS。
    `python3 scripts/release_check.py`: PASS。
- **完了再判定（2026-08-22）**:
  - 現行mainで対象3スイートを再実行し、`143 passed`（終了コード0）を確認した。
  - 3者qualification / confirmationは後続修正により全platform PASSへ更新済みであり、
    以前のAntigravity BLOCKEDは解消している。
  - ただし完了条件に対し、NFD拒否、platform別file identity、schemaと実装fieldの厳密な
    双方向照合、supported entrypoint inventoryの実体証明を行う陽性・陰性対照が不足している。
    現行テストはschema内部の`required == properties`と論理inventoryを検査するに留まるため、
    statusは`implementing`を維持する。
- **設計具体化（2026-08-22）**:
  - `FLW-DSN-017` v1.3で、非NFCを暗黙変換せずdecode境界で拒否する規則、3platformの閉じた
    file identity、active/reserved codec inventory、配布policyと実process probeによるentrypoint証明を固定した。
  - 後続タスク所有schemaを`reserved`としてproducer禁止にすることで、本タスクと後続lease実装の
    循環依存を解消した。設計再レビューとGate裁定までは実装再開せずstatusは`implementing`を維持する。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
