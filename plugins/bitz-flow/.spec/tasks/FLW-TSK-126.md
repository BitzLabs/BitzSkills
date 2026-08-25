---
implements: FLW-NFR-014
depends_on: [FLW-TSK-125]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/worktree_platform.py,plugins/bitz-flow/skills/flow-core/schemas/worktree-v2/platform-evidence-v2.schema.json,plugins/bitz-flow/skills/flow-core/references/worktree-v2-platform-support.json,tests/test_flow_m2_platform_adapter.py,tests/test_flow_m2_closed_result_contract.py,tests/test_flow_m2_probe_evidence.py,tests/test_flow_m2_operator_action.py,plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/docs/runbooks/m2-worktree-quarantine.md,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### 恒真のsemantic self-testを撤去しtmpfsをallowlistから外す

`FLW-REV-028:GP-007`。裁定: **案A（read-only維持）＋ tmpfsをallowlistから外す**。
実運用の範囲（Linux・repoの兄弟ディレクトリ・ext4）から逆算した判断であり、
実環境で発火しない検査を作らない。

- **実測した欠陥**:
  - `_semantic_self_test`は`_native_component`が変換に成功した値を同じcodecで往復させる
    だけで**恒真**である。§3.2 は「allowlistと起動時semantic self-testの両方で決める」と
    規定するが、実装は実質allowlistのみで決まっている。
  - `tmpfs`がallowlistに入っており、tmpfs上の0700ディレクトリは`SUPPORTED`になる。
    しかし§1.1 は「crash後も残るintentと安全側の緊急receiptを確定する」と保証しており、
    **tmpfsはマシン再起動で消える**ためこの保証が成立しない。
    worktree rootの既定は`<repo-parent>/.worktrees/...`（`FLW-DSN-006`）であり
    repoの兄弟＝ext4であるから、**tmpfsへ置く運用は想定にない**。
- **作業内容**:
  - `_semantic_self_test`を**関数ごと削除**し、`PlatformObservation`とschemaから
    `semantic_self_test` fieldを外す。恒真の検査を残すと「検査している」と誤読される。
  - `evaluate_platform`から`semantic-self-test-failed`理由を外す。
  - `tmpfs`をlinux allowlistから外す。
  - §3.2 を「allowlist ＋ 能力の可用性検査」へ書き直し、
    **lock/durabilityのsemanticsはallowlistを信頼している**ことを明記する。
    将来allowlistを広げるときの再検討条件を残す。
  - §1.1 の保証が成立する前提（永続化されるlocal filesystem）を明記する。
- **完了条件**:
  - `semantic_self_test`の参照が0件であること（機械検査）。
  - tmpfs上のrootが`filesystem-type-not-allowlisted`で不支持になること（実測）。
  - §3.2 が実装能力と一致していること。
- **見積り**: 実装PR 1本・1 session。新機能は作らない。
- **実行判定**: read-onlyのprobeを維持する。案B（隔離領域での実証）は
  `readonly-invariance`の受入行と衝突し、かつ実運用の範囲では発火しないため採らない。
