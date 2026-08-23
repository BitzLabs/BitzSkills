---
id: SI-FLW-084
raised_by: FLW-REV-027
target: flow-core platform adapter / CLI / production E2E
proposed_change_type: modify
status: open
---
- **目的**: `worktree.create` / `resume` が実環境のplatform能力を安全に観測し、production CLIからplanへclosed `PlatformEvidence`を渡せるようにする。
- **提案する修正**: OS別read-only probeを追加し、owner、filesystem、非追随walk、native/folded component、case semantics、lock、durability、child supervisionを観測する。観測不能は`UNSUPPORTED_FILESYSTEM`へ閉じ、doctorとplanで同じevidence生成器を使う。Windowsとcase-insensitive volumeを含むproduction dispatcher E2Eを追加する。
- **対象ファイル**: `worktree_platform.py`、`worktree_runtime.py`、`worktree_operability.py`、`cli.py`、platform support registry、関連schema/tests/confirmation。
- **確認観点**: fixture注入なしの既定dispatcherでplan/apply/unsupportedが到達すること。未知・network・観測不能をsupportedへ格上げしないこと。platform別native/folded componentからcollision keyを導出すること。
- **影響推定・ロールバック**: `FLW-NFR-014`依存10成果物と`FLW-FR-006`の公開経路に影響する。公開集合はgatedのまま維持し、変更はprobe・CLI結線単位でrevert可能にする。
- **依存**: `SI-FLW-085`。accept推薦（現行productionフローが必ず停止する実測に基づく）。
