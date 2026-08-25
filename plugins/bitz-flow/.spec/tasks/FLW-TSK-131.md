---
implements: FLW-NFR-014
depends_on: [FLW-TSK-130]
boundary: plugins/bitz-flow/.spec/design/FLW-DSN-017.md,plugins/bitz-flow/.spec/requirements/FLW-NFR-014.md,tests/test_flow_norm_consistency.py,plugins/bitz-flow/.claude-plugin/plugin.json,plugins/bitz-flow/plugin.json,plugins/bitz-flow/.codex-plugin/plugin.json
status: implementing
---

### Linux限定の裁定を規範へ反映し証跡の陳腐化を機械検査する

`FLW-REV-029:GP-003`（`SYN-003`）／`GP-004`（`SYN-004`）。**runtimeは変えない。**

- **実測した欠陥**:
  - `SYN-003`: 2026-08-24のLinux限定の裁定が§1.1／§13.5にしか適用されておらず、
    `FLW-NFR-014`:85の`verified`昇格条件、`FLW-DSN-017`§7のfixture要求、
    §13.7のGate blockingには「3 OS」が残っていた。**規範が互いに矛盾しており、
    どれを満たせば良いか決まらない。**
  - `SYN-004`: `FLW-TSK-126`でtmpfsをallowlistから外し、`FLW-TSK-125`でcase判定を
    mount局所へ変えたのに、§13.5の証跡欄は「ext4・tmpfsで`SUPPORTED`」
    「swapcase pathの存在で判定」のままだった。**撤回した事実を証跡が主張し続けていた。**
  - 共通の原因は「直した」あとに「他の箇所も直ったか」を確認していなかったこと。
- **作業内容**:
  - 3箇所（`FLW-NFR-014`:85、§7、§13.7）を保証対象platform（`SUPPORTED_SCOPE`）基準へ改める。
  - §13.5の証跡欄を現在の実装と実測へ揃える。
  - **再発を機械検査する**（`GP-004`の要求）。実装を正として規範文書の主張を照合する
    `tests/test_flow_norm_consistency.py`を追加する。
- **完了条件**:
  - 規範に保証範囲を広く読ませる記述が0件であること（機械検査）。
  - §13.5の保証対象／対象外ラベルが`SUPPORTED_SCOPE`と**厳密に一致**すること。
  - §13.5がallowlist外のfilesystemを`SUPPORTED`として記述しないこと。
  - §13.5が置き換え前のprobe方法を記述しないこと。
- **見積り**: 実装PR 1本・0.5 session。
- **実行判定**: 規範文書の主張の照合はsource照合でしか行えない。`GP-006`が制限するのは
  **実装の振る舞いをsource照合で代用すること**であり、本taskの対象は実装ではなく
  規範の記述そのものである。実装側の振る舞いは既存testが担う。
